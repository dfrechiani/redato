import asyncio
import base64
import json

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import WebSocket
from google.cloud.pubsub import PublisherClient
from redato_backend.shared.constants import GCP_PROJECT_ID
from redato_backend.shared.logger import logger


class BasePubSubManager(ABC):
    def __init__(self, project_id: str, subscription_name: str):
        self.active_connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()
        self.project_id = project_id
        self.subscription_name = subscription_name
        self._subscriber = None
        self._subscription_future = None
        self._executor = None

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """Connect a new client and start listening if this is the first connection"""
        await websocket.accept()
        async with self._lock:
            # Store the connection
            if user_id in self.active_connections:
                try:
                    await self.active_connections[user_id].close()
                except Exception as e:
                    logger.error(
                        f"Error closing existing connection for user {user_id}: {e}"
                    )

            self.active_connections[user_id] = websocket

            # Start listening if this is the first connection
            if len(self.active_connections) == 1:
                await self.start_listening()

            logger.info(f"New WebSocket connection established for user: {user_id}")

    async def disconnect(self, user_id: str) -> None:
        """Disconnect a client and stop listening if this was the last connection"""
        async with self._lock:
            if user_id in self.active_connections:
                try:
                    await self.active_connections[user_id].close()
                except Exception as e:
                    logger.error(f"Error closing connection for user {user_id}: {e}")
                finally:
                    del self.active_connections[user_id]

                    # Stop listening if no more connections
                    if not self.active_connections:
                        await self.stop_listening()

                    logger.info(f"WebSocket connection closed for user: {user_id}")

    async def start_listening(self):
        """Start listening only if not already listening"""
        if self._subscriber is not None:
            return

        try:
            from google.cloud import pubsub_v1

            self._executor = ThreadPoolExecutor()
            self._subscriber = pubsub_v1.SubscriberClient()

            subscription_path = self._subscriber.subscription_path(
                self.project_id, self.subscription_name
            )

            def callback(message: pubsub_v1.subscriber.message.Message):
                asyncio.create_task(self._process_pubsub_message(message))

            # Start subscribing in a separate thread
            self._subscription_future = self._subscriber.subscribe(
                subscription_path,
                callback=callback,
                flow_control=pubsub_v1.types.FlowControl(max_messages=100),
            )

            logger.info(
                f"Started listening to Pub/Sub subscription: {self.subscription_name}"
            )

        except Exception as e:
            logger.error(f"Error starting Pub/Sub listener: {e}")
            await self.stop_listening()

    async def stop_listening(self):
        """Stop listening and cleanup resources"""
        if self._subscriber:
            try:
                self._subscriber.close()
                self._subscriber = None
                if self._executor:
                    self._executor.shutdown(wait=False)
                    self._executor = None
                logger.info(
                    f"Stopped listening to Pub/Sub subscription: {self.subscription_name}"
                )
            except Exception as e:
                logger.error(f"Error stopping Pub/Sub listener: {e}")

    async def _process_pubsub_message(self, message: Any):
        """Process incoming Pub/Sub message"""
        try:
            # Only process if we have active connections
            if self.active_connections:
                data = json.loads(base64.b64decode(message.data).decode("utf-8"))
                user_id = data.get("user_id")

                if user_id and user_id in self.active_connections:
                    await self._handle_pubsub_message(user_id, data)

            message.ack()

        except Exception as e:
            logger.error(f"Error processing Pub/Sub message: {e}")
            message.ack()  # Ack even on error to avoid redelivery

    @abstractmethod
    async def _handle_pubsub_message(self, user_id: str, data: Dict[str, Any]):
        """Handle domain-specific message processing"""
        pass


class PubSub:
    def __init__(self) -> None:
        self._pubsub_client = PublisherClient()

    def publish(
        self,
        topic: str,
        message: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        message = {} if message is None else message
        topic_name = "projects/{}/topics/{}".format(GCP_PROJECT_ID, topic)
        future_publish = self._pubsub_client.publish(
            topic_name, json.dumps(message).encode("utf8"), **kwargs
        )
        message_id = future_publish.result()
        logger.info(f"PubSub message ID: {message_id}")


def default_serializer(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise ValueError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def publish_on_topic(topic: str, data: Any, **kwargs: Any) -> None:
    """
    Publish on pub sub topics
    :param topic: topic name
    :param data: data sent to topic
    :return: None
    """
    pub_sub = PubSub()
    try:
        logger.info(f"Publishing into topic '{topic}'...")
        pub_sub.publish(
            topic, json.loads(json.dumps(data, default=default_serializer)), **kwargs
        )
    except Exception as e:
        logger.error(f"Couldn't publish to topic '{topic}': {e}")
        raise e
