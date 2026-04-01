// Copyright (c) 2025 GenOrca (by zenoengine). All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "HAL/PlatformTime.h"

namespace MCPWorkbench
{

/** One inbound TCP connection (diagnostics). */
struct FConnectionRecord
{
	FDateTime ConnectedAt = FDateTime::Now();
	FString ClientEndpoint;
	bool bSuccess = true;
};

/** One handled MCP request (python / python_call / native). */
struct FRequestRecord
{
	FDateTime Timestamp = FDateTime::Now();
	FString RequestType;
	FString Module;
	FString Function;
	double DurationMs = 0.0;
	bool bSuccess = false;
	FString Message;
};

/**
 * Telemetry collector for MCP workbench diagnostics.
 * Tracks connection/request history and aggregate counters.
 * Owned by FMCPythonTcpServer; queried by SMCPWorkbenchWindow.
 */
class FTelemetry
{
public:
	void RecordConnection(const FString& ClientEndpoint)
	{
		TotalConnections++;
		FConnectionRecord Rec;
		Rec.ConnectedAt = FDateTime::Now();
		Rec.ClientEndpoint = ClientEndpoint;
		Rec.bSuccess = true;
		ConnectionHistory.Add(Rec);
		TrimHistory(ConnectionHistory);
	}

	void RecordRequest(const FRequestRecord& Record)
	{
		TotalRequests++;
		RequestHistory.Add(Record);
		TrimHistory(RequestHistory);
		if (Record.bSuccess)
		{
			SuccessfulRequests++;
		}
		else
		{
			FailedRequests++;
		}
	}

	void ClearAll()
	{
		ConnectionHistory.Empty();
		RequestHistory.Empty();
		TotalConnections = 0;
		TotalRequests = 0;
		SuccessfulRequests = 0;
		FailedRequests = 0;
	}

	int32 GetTotalConnections() const { return TotalConnections; }
	int32 GetTotalRequests() const { return TotalRequests; }
	int32 GetSuccessfulRequests() const { return SuccessfulRequests; }
	int32 GetFailedRequests() const { return FailedRequests; }

	const TArray<FConnectionRecord>& GetConnectionHistory() const { return ConnectionHistory; }
	const TArray<FRequestRecord>& GetRequestHistory() const { return RequestHistory; }

private:
	template<typename T>
	void TrimHistory(TArray<T>& History)
	{
		while (History.Num() > MaxHistoryItems)
		{
			History.RemoveAt(0);
		}
	}

	TArray<FConnectionRecord> ConnectionHistory;
	TArray<FRequestRecord> RequestHistory;

	int32 TotalConnections = 0;
	int32 TotalRequests = 0;
	int32 SuccessfulRequests = 0;
	int32 FailedRequests = 0;

	static constexpr int32 MaxHistoryItems = 500;
};

/**
 * RAII scope guard that auto-records a request on destruction.
 * Parses the incoming JSON data to extract type/module/function fields.
 */
class FRequestLogScope
{
public:
	FRequestLogScope(FTelemetry* InTelemetry, const FString& InData)
		: Telemetry(InTelemetry)
		, Data(InData)
		, StartSeconds(FPlatformTime::Seconds())
	{
	}

	/** Call before scope exits to record the execution outcome. */
	void SetResult(bool bInSuccess, const FString& InMessage)
	{
		bHasResult = true;
		bResultSuccess = bInSuccess;
		ResultMessage = InMessage;
	}

	~FRequestLogScope();

private:
	FTelemetry* Telemetry = nullptr;
	FString Data;
	double StartSeconds = 0.0;

	bool bHasResult = false;
	bool bResultSuccess = false;
	FString ResultMessage;
};

} // namespace MCPWorkbench

// Legacy type aliases for external consumers (XGameEditor, etc.)
using FMCPConnectionRecord = MCPWorkbench::FConnectionRecord;
using FMCPRequestRecord = MCPWorkbench::FRequestRecord;
