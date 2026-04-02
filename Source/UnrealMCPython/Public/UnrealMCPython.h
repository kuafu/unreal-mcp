// Copyright (c) 2025 GenOrca (by zenoengine). All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"
#include "MCPythonTcpServer.h"

class UNREALMCPYTHON_API FUnrealMCPythonModule : public IModuleInterface
{
public:
	/** IModuleInterface implementation */
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;

	/** Returns nullptr if the UnrealMCPython module is not loaded. */
	static FUnrealMCPythonModule* Get()
	{
		return FModuleManager::GetModulePtr<FUnrealMCPythonModule>(TEXT("UnrealMCPython"));
	}

	FMCPythonTcpServer* GetTcpServer() { return TcpServer.Get(); }

	/** Start the TCP server (no-op if already running). */
	void StartServer();

	/** Stop the TCP server (no-op if already stopped). */
	void StopServer();

private:
	TUniquePtr<FMCPythonTcpServer> TcpServer;

	static const uint16 DefaultPort = 12029;
	static const TCHAR* DefaultIP;
};
