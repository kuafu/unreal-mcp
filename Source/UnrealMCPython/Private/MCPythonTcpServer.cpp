// Copyright (c) 2025 GenOrca (by zenoengine). All Rights Reserved.

#include "MCPythonTcpServer.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "IPAddress.h"
#include "Common/TcpListener.h"
#include "IPythonScriptPlugin.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonReader.h"
#include "Dom/JsonObject.h"
#include "ILiveCodingModule.h"
#include "Containers/Ticker.h"
#include "HAL/PlatformTime.h"

DEFINE_LOG_CATEGORY_STATIC(LogMCPython, Log, All);

// MCPWorkbench::FRequestLogScope destructor — defined here to access JSON parsing.
MCPWorkbench::FRequestLogScope::~FRequestLogScope()
{
	if (!Telemetry)
	{
		return;
	}

	MCPWorkbench::FRequestRecord Rec;
	Rec.Timestamp = FDateTime::Now();
	Rec.DurationMs = (FPlatformTime::Seconds() - StartSeconds) * 1000.0;

	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Data);
	const bool bParsed = FJsonSerializer::Deserialize(Reader, JsonObj) && JsonObj.IsValid();
	if (bParsed)
	{
		JsonObj->TryGetStringField(TEXT("type"), Rec.RequestType);
		JsonObj->TryGetStringField(TEXT("module"), Rec.Module);
		JsonObj->TryGetStringField(TEXT("function"), Rec.Function);

		// For "python" type, show a snippet of the code as Function for readability
		if (Rec.RequestType == TEXT("python") && Rec.Function.IsEmpty())
		{
			FString Code;
			if (JsonObj->TryGetStringField(TEXT("code"), Code))
			{
				// First meaningful line (skip imports)
				Code.TrimStartAndEndInline();
				if (Code.Len() > 60)
				{
					Code = Code.Left(57) + TEXT("...");
				}
				Rec.Function = Code;
			}
		}
	}

	// Use execution result if SetResult() was called; otherwise fall back to parse status
	if (bHasResult)
	{
		Rec.bSuccess = bResultSuccess;
		Rec.Message = ResultMessage;
	}
	else if (bParsed)
	{
		Rec.bSuccess = true;
	}
	else
	{
		Rec.bSuccess = false;
		Rec.Message = TEXT("JSON parse error");
	}

	Telemetry->RecordRequest(Rec);
}

// Helper function to convert FJsonValue to Python literal string
FString ConvertJsonValueToPythonLiteral(const TSharedPtr<FJsonValue>& JsonVal)
{
    if (!JsonVal.IsValid() || JsonVal->Type == EJson::Null) return TEXT("None");

    switch (JsonVal->Type)
    {
        case EJson::String:
        {
            FString EscapedString = JsonVal->AsString();
            // Order of replacement is important.
            // Escape backslashes: "\" -> "\\"
            EscapedString = EscapedString.Replace(TEXT("\\"), TEXT("\\\\"));
            // Escape single quotes: ' -> \'
            EscapedString = EscapedString.Replace(TEXT("\'"), TEXT("\\\'"));
            // Escape double quotes: \" -> \\\"
            EscapedString = EscapedString.Replace(TEXT("\""), TEXT("\\\""));
            // Escape newlines: \n -> \\n
            EscapedString = EscapedString.Replace(TEXT("\n"), TEXT("\\n"));
            // Escape carriage returns: \r -> \\r
            EscapedString = EscapedString.Replace(TEXT("\r"), TEXT("\\r"));
            // Escape tabs: \t -> \\t
            EscapedString = EscapedString.Replace(TEXT("\t"), TEXT("\\t"));
            return FString::Printf(TEXT("\'%s\'"), *EscapedString);
        }
        case EJson::Number:
            return JsonVal->AsString();
        case EJson::Boolean:
            return JsonVal->AsBool() ? TEXT("True") : TEXT("False");
        case EJson::Array:
        {
            FString ArrayLiteral = TEXT("[");
            const auto& Array = JsonVal->AsArray();
            for (int32 i = 0; i < Array.Num(); ++i) {
                ArrayLiteral += ConvertJsonValueToPythonLiteral(Array[i]);
                if (i < Array.Num() - 1) ArrayLiteral += TEXT(", ");
            }
            ArrayLiteral += TEXT("]");
            return ArrayLiteral;
        }
        case EJson::Object:
        {
            FString DictLiteral = TEXT("{");
            const auto& Object = JsonVal->AsObject();
            bool bFirst = true;
            for (const auto& Pair : Object->Values) {
                if (!bFirst) DictLiteral += TEXT(", ");
                
                FString KeyString = Pair.Key;
                // Escape key string as well (similar to EJson::String case)
                KeyString = KeyString.Replace(TEXT("\\"), TEXT("\\\\"));
                KeyString = KeyString.Replace(TEXT("\'"), TEXT("\\\'"));
                KeyString = KeyString.Replace(TEXT("\""), TEXT("\\\""));
                KeyString = KeyString.Replace(TEXT("\n"), TEXT("\\n"));
                KeyString = KeyString.Replace(TEXT("\r"), TEXT("\\r"));
                KeyString = KeyString.Replace(TEXT("\t"), TEXT("\\t"));

                DictLiteral += FString::Printf(TEXT("\'%s\': %s"), *KeyString, *ConvertJsonValueToPythonLiteral(Pair.Value));
                bFirst = false;
            }
            DictLiteral += TEXT("}");
            return DictLiteral;
        }
        default:
            return TEXT("None");
    }
}

FMCPythonTcpServer::FMCPythonTcpServer()
{
    RegisterNativeHandlers();
}
FMCPythonTcpServer::~FMCPythonTcpServer() { Stop(); }

void FMCPythonTcpServer::RegisterNativeHandlers()
{
    NativeHandlers.Add(TEXT("livecoding_compile"), [this](TSharedPtr<FJsonObject> JsonObj, FSocket* ClientSocket)
    {
        HandleLiveCodingCompile(JsonObj, ClientSocket);
    });
}

void FMCPythonTcpServer::SendJsonResponse(TSharedPtr<FJsonObject> ResponseJson, FSocket* ClientSocket, bool bCloseSocket)
{
	FString ResultJson;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&ResultJson);
	FJsonSerializer::Serialize(ResponseJson.ToSharedRef(), Writer);
	Writer->Close();

	FTCHARToUTF8 ResultUtf8(*ResultJson);
	const uint8* DataPtr = (const uint8*)ResultUtf8.Get();
	int32 TotalSize = ResultUtf8.Length();
	int32 TotalSent = 0;
	while (TotalSent < TotalSize)
	{
		int32 SentNow = 0;
		if (!ClientSocket->Send(DataPtr + TotalSent, TotalSize - TotalSent, SentNow))
		{
			break;
		}
		if (SentNow == 0)
		{
			break;
		}
		TotalSent += SentNow;
	}

	if (bCloseSocket)
	{
		ClientSocket->Close();
		ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ClientSocket);
	}
}

bool FMCPythonTcpServer::Start(const FString& InIP, uint16 InPort)
{
    ListenIP = InIP;
    ListenPort = InPort;
    ServerStartTime = FDateTime::Now();

    FIPv4Address IPAddr;
    FIPv4Address::Parse(InIP, IPAddr);
    FIPv4Endpoint Endpoint(IPAddr, InPort);

    TcpListener = MakeShared<FTcpListener>(Endpoint, FTimespan::FromMilliseconds(100), false);
    TcpListener->OnConnectionAccepted().BindRaw(this, &FMCPythonTcpServer::HandleIncomingConnection);

    bShouldRun = true;
    UE_LOG(LogMCPython, Log, TEXT("TCP server started at %s:%d."), *InIP, InPort);
    return true;
}


void FMCPythonTcpServer::Stop()
{
	bShouldRun = false;
	TcpListener.Reset();
	UE_LOG(LogMCPython, Log, TEXT("TCP server stopped."));
}

bool FMCPythonTcpServer::HandleIncomingConnection(FSocket* ClientSocket, const FIPv4Endpoint& ClientEndpoint)
{
    UE_LOG(LogMCPython, Log, TEXT("Incoming connection from %s"), *ClientEndpoint.ToString());

    AsyncTask(ENamedThreads::GameThread, [this, ClientEndpoint]()
    {
        Telemetry.RecordConnection(ClientEndpoint.ToString());
    });

    AsyncTask(ENamedThreads::AnyBackgroundThreadNormalTask, [this, ClientSocket, ClientEndpoint]() {
        TArray<uint8> ReceivedData;

        uint32 DataSize = 0;
        while (ClientSocket->HasPendingData(DataSize) || ReceivedData.IsEmpty())
        {
            TArray<uint8> Buffer;
            Buffer.SetNumZeroed(DataSize);
            int32 BytesRead = 0;
            ClientSocket->Recv(Buffer.GetData(), Buffer.Num(), BytesRead);
            Buffer.SetNum(BytesRead);
            ReceivedData.Append(Buffer);
        }
        ReceivedData.Add(NULL);

        FString ReceivedString = FString(UTF8_TO_TCHAR(reinterpret_cast<const char*>(ReceivedData.GetData())));

        // Defer Python execution to the next engine tick via FTSTicker instead of
        // running it immediately inside an AsyncTask(GameThread) lambda.
        // Destructive operations like load_level tear down and rebuild the World
        // synchronously — if this happens inside an AsyncTask dispatched mid-tick,
        // it re-enters the engine loop and causes access violations in CoreUObject.
        // FTSTicker fires at a clean frame boundary, avoiding re-entrancy.
        FTSTicker::GetCoreTicker().AddTicker(
            FTickerDelegate::CreateLambda(
                [this, ReceivedString, ClientSocket, ClientEndpoint](float) -> bool
                {
                    ProcessDataOnGameThread(ReceivedString, ClientSocket, ClientEndpoint);
                    return false; // one-shot
                }),
            0.0f // next tick
        );
    });

    return true;
}

void FMCPythonTcpServer::ProcessDataOnGameThread(const FString& Data, FSocket* ClientSocket, const FIPv4Endpoint& ClientEndpoint)
{
    MCPWorkbench::FRequestLogScope RequestLog(&Telemetry, Data);

    UE_LOG(LogMCPython, Verbose, TEXT("Processing Data on Game Thread: %s"), *Data);

    TSharedPtr<FJsonObject> JsonObj;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Data);
    FString TypeField;
    FString CodeField;
    FString ResultMsg;
    bool bExecSuccess = false;

    if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
    {
        RequestLog.SetResult(false, TEXT("JSON parse error on received data"));
        TSharedPtr<FJsonObject> ErrorResponse = MakeShareable(new FJsonObject);
        ErrorResponse->SetBoolField(TEXT("success"), false);
        ErrorResponse->SetStringField(TEXT("message"), TEXT("Failed: JSON parse error on received data"));
        ErrorResponse->SetStringField(TEXT("raw_data"), Data);
        SendJsonResponse(ErrorResponse, ClientSocket);
        return;
    }

    if (!JsonObj->TryGetStringField(TEXT("type"), TypeField))
    {
        RequestLog.SetResult(false, TEXT("Missing 'type' field"));
        TSharedPtr<FJsonObject> ErrorResponse = MakeShareable(new FJsonObject);
        ErrorResponse->SetBoolField(TEXT("success"), false);
        ErrorResponse->SetStringField(TEXT("message"), TEXT("Failed: Missing 'type' field in JSON request"));
        SendJsonResponse(ErrorResponse, ClientSocket);
        return;
    }

    // --- Native command handlers (e.g. livecoding_compile) ---
    if (FNativeCommandHandler* Handler = NativeHandlers.Find(TypeField))
    {
        RequestLog.SetResult(true, FString::Printf(TEXT("Native: %s"), *TypeField));
        (*Handler)(JsonObj, ClientSocket);
        return;
    }

    // --- Build Python code string ---
    if (TypeField == TEXT("python"))
    {
        if (!JsonObj->TryGetStringField(TEXT("code"), CodeField))
        {
            ResultMsg = TEXT("Failed: 'code' field missing for type 'python'");
            CodeField = TEXT("import json; print(json.dumps({'success': False, 'message': 'Error: code field missing'}))");
        }
    }
    else if (TypeField == TEXT("python_call"))
    {
        FString ModuleName, FunctionName;
        if (JsonObj->TryGetStringField(TEXT("module"), ModuleName) &&
            JsonObj->TryGetStringField(TEXT("function"), FunctionName))
        {
            const TSharedPtr<FJsonObject>* ArgsJsonObjectPtr = nullptr;
            JsonObj->TryGetObjectField(TEXT("args"), ArgsJsonObjectPtr);

            FString PyArgsStringForCall;
            if (ArgsJsonObjectPtr && ArgsJsonObjectPtr->IsValid())
            {
                TSharedPtr<FJsonValueObject> ArgsJsonValue = MakeShareable(new FJsonValueObject(*ArgsJsonObjectPtr));
                PyArgsStringForCall = ConvertJsonValueToPythonLiteral(ArgsJsonValue);
            }
            else
            {
                PyArgsStringForCall = TEXT("{}");
            }

            CodeField = FString::Printf(TEXT("from UnrealMCPython import mcp_unreal_actions;print(mcp_unreal_actions.execute_action(\'%s\', \'%s\', %s));"),
                                        *ModuleName,
                                        *FunctionName,
                                        *PyArgsStringForCall);

            UE_LOG(LogMCPython, Verbose, TEXT("Generated Python Call (via execute_action):\\n%s"), *CodeField);
        }
        else
        {
            ResultMsg = TEXT("Failed: Missing 'module' or 'function' field for type 'python_call'");
            CodeField = TEXT("import json; print(json.dumps({'success': False, 'message': 'Error: module/function field missing'}))");
        }
    }
    else
    {
        RequestLog.SetResult(false, FString::Printf(TEXT("Unsupported type: %s"), *TypeField));
        TSharedPtr<FJsonObject> ErrorResponse = MakeShareable(new FJsonObject);
        ErrorResponse->SetBoolField(TEXT("success"), false);
        ErrorResponse->SetStringField(TEXT("message"), FString::Printf(TEXT("Failed: Unsupported type: %s"), *TypeField));
        SendJsonResponse(ErrorResponse, ClientSocket);
        return;
    }

    // --- Execute Python ---
    IPythonScriptPlugin* PythonPlugin = IPythonScriptPlugin::Get();
    if (!PythonPlugin)
    {
        TSharedPtr<FJsonObject> ErrorResponse = MakeShareable(new FJsonObject);
        ErrorResponse->SetBoolField(TEXT("success"), false);
        ErrorResponse->SetStringField(TEXT("message"), TEXT("Failed: PythonScriptPlugin not found"));
        SendJsonResponse(ErrorResponse, ClientSocket);
        return;
    }

    // Send the response BEFORE executing destructive Python commands (e.g. load_level).
    // load_level tears down the current World synchronously inside ExecPythonCommandEx,
    // which can invalidate editor state and crash if we try to use the socket afterward.
    // By pre-sending a response and closing the socket first, we guarantee the client
    // gets a reply regardless of what happens during execution.

    // Capture logs to get Python output
    LogCapture.Clear();
    GLog->AddOutputDevice(&LogCapture);

    FPythonCommandEx PythonCommand;
    PythonCommand.Command = CodeField;
    PythonCommand.ExecutionMode = EPythonCommandExecutionMode::ExecuteFile;

    bExecSuccess = PythonPlugin->ExecPythonCommandEx(PythonCommand);

    GLog->RemoveOutputDevice(&LogCapture);

    FString CapturedLogs = LogCapture.GetLogs().TrimStartAndEnd();

    // --- Build response ---
    // Wrap non-JSON output so the client always gets valid JSON in the "result" field.
    bool bIsJson = CapturedLogs.StartsWith(TEXT("{")) || CapturedLogs.StartsWith(TEXT("["));
    if (!bIsJson)
    {
        TSharedPtr<FJsonObject> WrappedObj = MakeShareable(new FJsonObject);
        WrappedObj->SetBoolField(TEXT("success"), false);
        WrappedObj->SetStringField(TEXT("message"), TEXT("Python did not return JSON"));
        WrappedObj->SetStringField(TEXT("raw_result"), CapturedLogs);
        FString WrappedJson;
        TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&WrappedJson);
        FJsonSerializer::Serialize(WrappedObj.ToSharedRef(), Writer);
        Writer->Close();
        CapturedLogs = WrappedJson;
    }

    if (bExecSuccess)
    {
        UE_LOG(LogMCPython, Log, TEXT("Python OK (%s)"), *TypeField);
    }
    else
    {
        UE_LOG(LogMCPython, Warning, TEXT("Python FAILED (%s). Output: %s"), *TypeField, *CapturedLogs);
    }

    TSharedPtr<FJsonObject> ResponseToClient = MakeShareable(new FJsonObject);
    ResponseToClient->SetBoolField(TEXT("success"), bExecSuccess);

    FString ResponseMessage;
    if (!ResultMsg.IsEmpty())
    {
        ResponseMessage = ResultMsg;
    }
    else if (!bExecSuccess)
    {
        // Extract a concise error message from captured logs for the workbench
        FString ErrorSummary;
        if (!CapturedLogs.IsEmpty())
        {
            // Try to find the last "Error:" line for a concise summary
            TArray<FString> Lines;
            CapturedLogs.ParseIntoArrayLines(Lines);
            for (int32 i = Lines.Num() - 1; i >= 0; --i)
            {
                if (Lines[i].Contains(TEXT("Error:")) && !Lines[i].Contains(TEXT("Traceback")))
                {
                    ErrorSummary = Lines[i].TrimStartAndEnd();
                    // Strip "LogPython: Error: " prefix if present
                    ErrorSummary.ReplaceInline(TEXT("LogPython: Error: "), TEXT(""));
                    break;
                }
            }
            ResponseMessage = TEXT("Python execution failed. See result for details.");
        }
        else
        {
            ResponseMessage = TEXT("Python execution failed with no specific error log.");
        }

        // Record the concise error in the workbench
        RequestLog.SetResult(false, ErrorSummary.IsEmpty() ? ResponseMessage : ErrorSummary);
    }
    else
    {
        ResponseMessage = TEXT("Python command executed successfully.");
        RequestLog.SetResult(true, TEXT("OK"));
    }

    ResponseToClient->SetStringField(TEXT("message"), ResponseMessage);
    ResponseToClient->SetStringField(TEXT("result"), CapturedLogs);

    // Send response and close socket.
    // NOTE: We must send the response before the socket/world becomes invalid.
    // Destructive operations like load_level can tear down the current World during
    // ExecPythonCommandEx above, but the response data is already captured, so
    // sending it here is safe as long as the socket is still valid.
    SendJsonResponse(ResponseToClient, ClientSocket);
}

void FMCPythonTcpServer::HandleLiveCodingCompile(TSharedPtr<FJsonObject> JsonObj, FSocket* ClientSocket)
{
    ILiveCodingModule* LiveCoding = FModuleManager::GetModulePtr<ILiveCodingModule>(TEXT("LiveCoding"));
    if (!LiveCoding)
    {
        TSharedPtr<FJsonObject> Response = MakeShareable(new FJsonObject);
        Response->SetBoolField(TEXT("success"), false);
        Response->SetStringField(TEXT("message"), TEXT("LiveCoding module is not available."));
        SendJsonResponse(Response, ClientSocket);
        return;
    }

    if (!LiveCoding->IsEnabledForSession())
    {
        TSharedPtr<FJsonObject> Response = MakeShareable(new FJsonObject);
        Response->SetBoolField(TEXT("success"), false);
        Response->SetStringField(TEXT("message"), TEXT("LiveCoding is not enabled for this session. Enable it in Editor Preferences > Live Coding."));
        SendJsonResponse(Response, ClientSocket);
        return;
    }

    ELiveCodingCompileResult CompileResult;
    LiveCoding->Compile(ELiveCodingCompileFlags::None, &CompileResult);

    if (CompileResult == ELiveCodingCompileResult::CompileStillActive)
    {
        TSharedPtr<FJsonObject> Response = MakeShareable(new FJsonObject);
        Response->SetBoolField(TEXT("success"), false);
        Response->SetStringField(TEXT("message"), TEXT("LiveCoding compilation is already in progress."));
        SendJsonResponse(Response, ClientSocket);
        return;
    }

    if (CompileResult == ELiveCodingCompileResult::NotStarted)
    {
        TSharedPtr<FJsonObject> Response = MakeShareable(new FJsonObject);
        Response->SetBoolField(TEXT("success"), false);
        Response->SetStringField(TEXT("message"), TEXT("Failed to start LiveCoding compilation. Live coding monitor could not be started."));
        SendJsonResponse(Response, ClientSocket);
        return;
    }

    // InProgress: poll until done
    UE_LOG(LogMCPython, Log, TEXT("LiveCoding compile started. Waiting for completion..."));

    double StartTime = FPlatformTime::Seconds();
    double TimeoutSeconds = 120.0;

    FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateLambda(
            [this, ClientSocket, LiveCoding, StartTime, TimeoutSeconds](float DeltaTime) -> bool
            {
                if (LiveCoding->IsCompiling())
                {
                    double ElapsedTime = FPlatformTime::Seconds() - StartTime;
                    if (ElapsedTime > TimeoutSeconds)
                    {
                        TSharedPtr<FJsonObject> Response = MakeShareable(new FJsonObject);
                        Response->SetBoolField(TEXT("success"), false);
                        Response->SetStringField(TEXT("message"),
                            FString::Printf(TEXT("LiveCoding compilation timed out after %.0f seconds."), TimeoutSeconds));
                        SendJsonResponse(Response, ClientSocket);
                        return false;
                    }
                    return true;
                }

                double ElapsedTime = FPlatformTime::Seconds() - StartTime;
                TSharedPtr<FJsonObject> Response = MakeShareable(new FJsonObject);
                Response->SetBoolField(TEXT("success"), true);
                Response->SetStringField(TEXT("message"),
                    FString::Printf(TEXT("LiveCoding compilation finished in %.1f seconds. Check get_output_log for the result. If compilation failed, use Build.bat or msbuild-mcp-server to check detailed error messages."), ElapsedTime));
                Response->SetNumberField(TEXT("elapsed_seconds"), ElapsedTime);
                SendJsonResponse(Response, ClientSocket);
                return false;
            }),
        0.5f
    );
}