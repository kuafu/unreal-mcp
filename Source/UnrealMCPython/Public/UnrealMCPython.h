// Copyright (c) 2025 GenOrca (by zenoengine). All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"
#include "MCPythonTcpServer.h"

class FUnrealMCPythonModule : public IModuleInterface
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

private:
	TUniquePtr<FMCPythonTcpServer> TcpServer;
};
