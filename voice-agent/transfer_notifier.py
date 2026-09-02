import aiohttp
import logging
from enum import Enum
from abc import ABC, abstractmethod
from models import TransferMessage
from dotenv import load_dotenv
import os

logger = logging.getLogger(__name__)

load_dotenv()


# ==========================================================
# Enum for notifier types
# ==========================================================

class NotificationType(Enum):
    SLACK = "slack"
    TEAMS = "teams"


# ==========================================================
# Strategy Interface
# ==========================================================

class NotificationStrategy(ABC):

    @abstractmethod
    async def send_transfer_notification(self, message: TransferMessage):
        pass


# ==========================================================
# Slack Strategy
# ==========================================================

class SlackNotifier(NotificationStrategy):

    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    async def send_transfer_notification(self, message: TransferMessage):

        formatted_text = (
            f"*Transfer Initiated*\n"
            f"Load Number: {message.load_number}\n"
            f"Reason: {message.reason_of_transfer}\n"
            f"Carrier asked Price: {message.price_asked_by_carrier}\n"
            f"Bot Best Price: {message.best_price_offered_by_bot}"
        )

        payload = {"text": formatted_text}

        async with aiohttp.ClientSession() as session:
            async with session.post(self.webhook_url, json=payload) as resp:
                if resp.status != 200:
                    logger.error("Slack notification failed")


# ==========================================================
# Teams Strategy
# ==========================================================

class TeamsNotifier(NotificationStrategy):

    def __init__(self):
        self.webhook_url = "TEAMS_WEBHOOK_URL"

    async def send_transfer_notification(self, message: TransferMessage):

        logger.info("Slack notification placeholder")


# ==========================================================
# Strategy Factory
# ==========================================================

class NotifierFactory:

    @staticmethod
    def get_notifier(notification_type: NotificationType) -> NotificationStrategy:

        if notification_type == NotificationType.SLACK:
            return SlackNotifier()

        if notification_type == NotificationType.TEAMS:
            return TeamsNotifier()

        raise ValueError(f"Unsupported notification type: {notification_type}")


# ==========================================================
# Context
# ==========================================================

class TransferNotifier:

    def __init__(self, notification_type: NotificationType):
        self.strategy = NotifierFactory.get_notifier(notification_type)

    async def notify(self, message: TransferMessage):
        await self.strategy.send_transfer_notification(message)