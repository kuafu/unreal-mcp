// Copyright (c) 2025 GenOrca (by zenoengine). All Rights Reserved.

#pragma once

#include "CoreMinimal.h"

/** One inbound TCP connection (MCP workbench / diagnostics). */
struct FMCPConnectionRecord
{
	FDateTime ConnectedAt = FDateTime::Now();
	FString ClientEndpoint;
	bool bSuccess = true;
};

/** One handled MCP request (python / python_call / native). */
struct FMCPRequestRecord
{
	FDateTime Timestamp = FDateTime::Now();
	FString RequestType;
	FString Module;
	FString Function;
	double DurationMs = 0.0;
	bool bSuccess = false;
	FString Message;
};
