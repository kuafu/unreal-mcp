// Copyright (c) 2025 GenOrca (by zenoengine). All Rights Reserved.

#include "UnrealMCPython.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "Common/TcpListener.h"
#include "IPythonScriptPlugin.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonReader.h"
#include "Dom/JsonObject.h"
#include "MCPythonTcpServer.h"

#define LOCTEXT_NAMESPACE "FUnrealMCPythonModule"

const TCHAR* FUnrealMCPythonModule::DefaultIP = TEXT("127.0.0.1");

void FUnrealMCPythonModule::StartupModule()
{
	TcpServer = MakeUnique<FMCPythonTcpServer>();
	TcpServer->Start(DefaultIP, DefaultPort);
}

void FUnrealMCPythonModule::ShutdownModule()
{
	if (TcpServer)
	{
		TcpServer->Stop();
		TcpServer.Reset();
	}
}

void FUnrealMCPythonModule::StartServer()
{
	if (TcpServer && TcpServer->IsRunning())
	{
		return;
	}
	if (!TcpServer)
	{
		TcpServer = MakeUnique<FMCPythonTcpServer>();
	}
	TcpServer->Start(DefaultIP, DefaultPort);
}

void FUnrealMCPythonModule::StopServer()
{
	if (TcpServer && TcpServer->IsRunning())
	{
		TcpServer->Stop();
	}
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FUnrealMCPythonModule, UnrealMCPython)