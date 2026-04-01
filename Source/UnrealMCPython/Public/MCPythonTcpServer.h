// Copyright (c) 2025 GenOrca (by zenoengine). All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Interfaces/IPv4/IPv4Endpoint.h"
#include "MCPythonWorkbenchTypes.h"
#include <memory>
#include "Misc/OutputDeviceRedirector.h"

class FTcpListener;
class FSocket;

class FPythonLogCapture : public FOutputDevice
{
public:
	FPythonLogCapture() : FOutputDevice() {}

	virtual void Serialize(const TCHAR* InData, ELogVerbosity::Type Verbosity, const FName& Category) override
	{
		if (Category == FName("LogPython"))
		{
			CapturedLogs.Append(InData);
			CapturedLogs.Append(TEXT("\n"));
		}
	}

	void Clear() { CapturedLogs.Empty(); }
	FString GetLogs() const { return CapturedLogs; }

private:
	FString CapturedLogs;
};

using FNativeCommandHandler = TFunction<void(TSharedPtr<FJsonObject> JsonObj, FSocket* ClientSocket)>;

class FMCPythonTcpServer
{
public:
	FMCPythonTcpServer();
	~FMCPythonTcpServer();

	bool Start(const FString& InIP, uint16 InPort);
	void Stop();

	bool IsRunning() const { return TcpListener.IsValid() && bShouldRun; }

	const FString& GetListenIP() const { return ListenIP; }
	uint16 GetListenPort() const { return ListenPort; }
	FDateTime GetStartTime() const { return ServerStartTime; }

	int32 GetTotalConnections() const { return TotalConnections; }
	int32 GetTotalRequests() const { return TotalRequests; }
	int32 GetSuccessfulRequests() const { return SuccessfulRequests; }
	int32 GetFailedRequests() const { return FailedRequests; }

	const TArray<FMCPConnectionRecord>& GetConnectionHistory() const { return ConnectionHistory; }
	const TArray<FMCPRequestRecord>& GetRequestHistory() const { return RequestHistory; }

	void ClearHistory()
	{
		ConnectionHistory.Empty();
		RequestHistory.Empty();
		TotalConnections = 0;
		TotalRequests = 0;
		SuccessfulRequests = 0;
		FailedRequests = 0;
	}

	/** Used by MCP workbench request logging (scope exit). */
	void AppendRequestRecord(const FMCPRequestRecord& Record);

private:
	TSharedPtr<FTcpListener> TcpListener;
	FSocket* ListenSocket = nullptr;
	bool bShouldRun = false;
	FPythonLogCapture LogCapture;
	TMap<FString, FNativeCommandHandler> NativeHandlers;

	void RegisterNativeHandlers();
	bool HandleIncomingConnection(FSocket* ClientSocket, const FIPv4Endpoint& ClientEndpoint);
	void ProcessDataOnGameThread(const FString& Data, FSocket* ClientSocket, const FIPv4Endpoint& ClientEndpoint);
	void SendJsonResponse(TSharedPtr<FJsonObject> ResponseJson, FSocket* ClientSocket, bool bCloseSocket = true);

	void RecordConnectionOnGameThread(const FIPv4Endpoint& ClientEndpoint);

	// Native command handlers
	void HandleLiveCodingCompile(TSharedPtr<FJsonObject> JsonObj, FSocket* ClientSocket);

	FString ListenIP;
	uint16 ListenPort = 0;
	FDateTime ServerStartTime;

	int32 TotalConnections = 0;
	int32 TotalRequests = 0;
	int32 SuccessfulRequests = 0;
	int32 FailedRequests = 0;

	TArray<FMCPConnectionRecord> ConnectionHistory;
	TArray<FMCPRequestRecord> RequestHistory;

	static constexpr int32 MaxHistoryItems = 500;
};