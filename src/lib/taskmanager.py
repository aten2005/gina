from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain import hub
from langchain_openai import ChatOpenAI
from composio_langchain import ComposioToolSet, Action, App, Tag
from composio import Composio, App
from dotenv import load_dotenv
import os

from typing import *
import logging
import asyncio
import discord
from discord.ext import commands

import datetime
import pytz

load_dotenv()

llm = ChatOpenAI(openai_api_key=os.environ["OPENAI_API_KEY"])
composio_client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])

# Configure logging
logging.basicConfig(level=logging.INFO)

class ComposioAgent:
    
    def __init__(self, entity_id: str, discord_channel, bot):
        """
        Initializes a new instance of the ComposioAgent class.

        Args:
            entity_id(str): Unique id for discord acc.
            discord_channel: The Discord channel object.
            bot: The Discord bot object.

        Returns:
            None
        """
        self.entity_id = self.entity_id
        self.entity = None
        self.connected_accounts = {}  # Manually track connected accounts
        self.connected_account = None
        self.composio_toolset = None
        self.actions = None
        self.discord_channel = discord_channel
        self.bot = bot
        
        
    async def wait_for_connection_active(self, connection_request, timeout: int = 120) -> str:
        """
        Asynchronously waits for a connection request to become active.
        Args:
            connection_request (ConnectionRequest): The connection request to wait for.
            timeout (int, optional): The maximum time to wait in seconds. Defaults to 120.
        Returns:
            str: The connected account if it becomes active within the timeout period, otherwise None.

        """
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            connected_account = connection_request.wait_until_active(client=composio_client, timeout=timeout)
            if connected_account.status == "ACTIVE":
                print(connected_account)
                return connected_account
        return None

    def create_entity_if_not_exists(self) -> bool:
        """
        Creates a new entity if it does not already exist.
        This function checks if an entity with the given entity ID exists in the Composio client. If it does, the function logs a message indicating that the entity exists. If the entity does not exist, the function attempts to create a new entity with the given entity ID. If the entity is successfully created, the function logs a message indicating that a new entity was created. If an error occurs while creating the entity, the function logs an error message and returns False.
        Returns:
            bool: True if the entity was created or already exists, False if an error occurred while creating the entity.
        """
        try:
            self.entity = composio_client.get_entity(id=self.entity_id)
            logging.info(f"Entity for user {self.entity_id} exists.")
        except Exception:
            # Create new entity
            try:
                self.entity = composio_client.create_entity(id=self.entity_id)
                logging.info(f"Created new entity for user {self.entity_id}.")
            except Exception as e:
                logging.error(f"Failed to create entity: {e}")
                return False
        return True

    # async def collect_params_from_user(self, required_params, app):
    #     """
    #     Collects parameters from the user by prompting them for each required parameter.

    #     Args:
    #         required_params (List[Dict[str, str]]): A list of dictionaries containing the required parameters.
    #         app (str): The name of the application.

    #     Returns:
    #         Dict[str, str]: A dictionary containing the user-provided parameter values.

    #     Raises:
    #         asyncio.TimeoutError: If the user does not respond within the specified timeout.

    #     """
    #     params = {}
    #     for param in required_params:
    #         prompt = f"Please provide {param['displayName']} for {app}:"
    #         await self.discord_channel.send(prompt)
            
    #         def check(m):
    #             return m.author != self.discord_channel.guild.me and m.channel == self.discord_channel

    #         try:
    #             response = await self.bot.wait_for('message', check=check, timeout=300.0)
    #             params[param["name"]] = response.content.strip()
    #         except asyncio.TimeoutError:
    #             await self.discord_channel.send("Timeout. Please try again and provide your details promptly.")
    #             raise
    #     return params

    async def connect(self,author) -> bool:
        """
        Asynchronously connects to Composio services for the user.
        This function first checks if an entity for the user already exists in the Composio client. If it does, the function logs a message indicating that the entity exists. If the entity does not exist, the function attempts to create a new entity with the given user ID. If the entity is successfully created, the function logs a message indicating that a new entity was created. If an error occurs while creating the entity, the function logs an error message and returns False.
        After the entity is created or found, the function connects to the specified apps by initiating a connection for each app. If a connection request has a redirect URL, the function sends a message to the Discord channel with the URL and waits for the connection to become active. If the connection request does not have a redirect URL, the function retrieves the connected account ID directly from the connection request. The function then stores the connected account ID in the `connected_accounts` dictionary.
        After all the connections are established, the function retrieves the prompt from the `hub` and initializes the `composio_toolset` with the entity ID. The function then retrieves the tools for the specified apps using the `get_tools` method of the `composio_toolset`. Finally, the function logs a message indicating that the connection was successful.
        Returns:
            bool: True if the connection was successful, False if an error occurred while creating the entity or connecting to the apps.
        """
        if not self.create_entity_if_not_exists():
            return False

        try:
            # Define the apps you want to connect
            apps = ["gmail", "googlecalendar"]
            
            for app in apps:
                if app not in self.connected_accounts:
                    
                    all_integrations = composio_client.integrations.get()
                    # Find the integration for the current app
                    integration = next((i for i in all_integrations if i.appName == app), None)
                    if not integration:
                        logging.error(f"Integration for {app} not found")
                        continue
                    
                    connection_request = self.entity.initiate_connection(app_name=app)
                    print(connection_request)
                    if connection_request.redirectUrl:
                        embed=discord.Embed(title="Link",url=f"{connection_request.redirectUrl}",description="Please click on the link to complete the auth flow",color=0xFF0000)
                        await author.send(embed=embed)
                        
                        connection_account = await self.wait_for_connection_active(connection_request, 120)
                        
                    else:
                        connection_account = connection_request.connectedAccountId

                    # Wait and poll for the connection status
                    self.connected_accounts[app] = connection_account


            self.prompt = hub.pull("hwchase17/openai-functions-agent")
            self.composio_toolset = ComposioToolSet(entity_id=self.entity_id)
            self.actions = self.composio_toolset.get_tools(apps=[App.GMAIL, App.GOOGLECALENDAR])  
            logging.info(f"Successfully connected to Composio services for user {self.entity_id}")
        except Exception as e:
            logging.error(f"Connection failed: {e}")
            return False

        return True

    async def doTask(self, command: str) -> bool:
        """
        Asynchronously executes a task using the OpenAI functions agent.
        Args:
            command (str): The command to be executed.
        Returns:
            bool: True if the task is completed successfully, False otherwise.
        Raises:
            Exception: If an error occurs while executing the task.
        This method creates an OpenAI functions agent using the provided language model, actions, and prompt. It then creates an AgentExecutor with the agent and the provided actions. The task is invoked by passing the command as input. If the task is completed successfully, a success message is logged with the user and the command. If an exception occurs, an error message is logged with the exception and False is returned.
        Note:
            This method assumes that the necessary dependencies and variables are already imported and initialized.
        """
        try:
            agent = create_openai_functions_agent(llm, self.actions, self.prompt)
            agent_executor = AgentExecutor(agent=agent, tools=self.actions, verbose=True)
            print("printing....")
            res = agent_executor.invoke({"input": f"The current date and time is {datetime.datetime.now(pytz.UTC)}" + command})
            logging.info(f"Task '{command}' completed successfully for user {self.entity_id}")
            return res["output"]
        except Exception as e:
            logging.error(f"Failed to complete task: {e}")
            return False
