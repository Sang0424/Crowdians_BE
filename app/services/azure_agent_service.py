# app/services/azure_agent_service.py
"""
Azure AI Projects SDK Service for Hosted Agents.
Provides utilities to deploy, list, and delete container-based hosted agents on Azure.
"""

import os
from typing import Any, Dict, List, Optional
from azure.identity.aio import DefaultAzureCredential
from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import (
    ImageBasedHostedAgentDefinition,
    ProtocolVersionRecord,
    AgentProtocol,
)

class AzureHostedAgentService:
    """
    Service class to interact with Azure AI Projects hosted agents.
    Uses asynchronous clients and DefaultAzureCredential for secure token acquisition.
    """

    def __init__(self, endpoint: Optional[str] = None):
        # Fallback to environment variable if not provided
        self.endpoint = endpoint or os.getenv("AZURE_AI_PROJECT_ENDPOINT")

    def _get_client(self, credential: DefaultAzureCredential) -> AIProjectClient:
        if not self.endpoint:
            raise ValueError("AZURE_AI_PROJECT_ENDPOINT is not configured.")
        return AIProjectClient(
            endpoint=self.endpoint,
            credential=credential
        )

    async def create_hosted_agent(
        self,
        agent_name: str,
        image_uri: str,
        cpu: str = "1",
        memory: str = "2Gi",
        tools: Optional[List[Dict[str, Any]]] = None,
        environment_variables: Optional[Dict[str, str]] = None
    ) -> Any:
        """
        Deploys a container-based hosted agent with custom specifications.
        """
        if tools is None:
            tools = [{"type": "code_interpreter"}]

        if environment_variables is None:
            environment_variables = {}

        # Add default endpoints/configs to env vars if available
        if self.endpoint and "AZURE_AI_PROJECT_ENDPOINT" not in environment_variables:
            environment_variables["AZURE_AI_PROJECT_ENDPOINT"] = self.endpoint

        async with DefaultAzureCredential() as credential:
            async with self._get_client(credential) as client:
                definition = ImageBasedHostedAgentDefinition(
                    container_protocol_versions=[
                        ProtocolVersionRecord(
                            protocol=AgentProtocol.RESPONSES,
                            version="v1"
                        )
                    ],
                    image=image_uri,
                    cpu=cpu,
                    memory=memory,
                    tools=tools,
                    environment_variables=environment_variables
                )
                
                agent = await client.agents.create_version(
                    agent_name=agent_name,
                    definition=definition
                )
                return agent

    async def list_agent_versions(self, agent_name: str) -> List[Any]:
        """
        Retrieves all deployed versions of the specified agent.
        """
        async with DefaultAzureCredential() as credential:
            async with self._get_client(credential) as client:
                versions = await client.agents.list_versions(agent_name=agent_name)
                return versions

    async def delete_agent_version(self, agent_name: str, version: str) -> None:
        """
        Deletes a specific version of a hosted agent.
        """
        async with DefaultAzureCredential() as credential:
            async with self._get_client(credential) as client:
                await client.agents.delete_version(
                    agent_name=agent_name,
                    version=version
                )
