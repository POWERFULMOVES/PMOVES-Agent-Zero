from helpers.extension import Extension
from plugins._model_config.helpers import model_config


class MissingApiKeyCheck(Extension):
    """Check if API keys are configured for selected model providers."""

    ONBOARDING_MODAL_PATH = "/plugins/_onboarding/webui/onboarding.html"
    ONBOARDING_CTA_TEXT = "Start Onboarding"

    async def execute(self, banners: list = [], frontend_context: dict = {}, **kwargs):
        missing_providers = model_config.get_missing_api_key_providers()

        if missing_providers:
            banners.append({
                "id": "missing-api-key",
                "type": "warning",
                "priority": 100,
                "title": "Welcome to Agent Zero!",
                "html": f"""You're almost ready to chat. Please configure your models to continue.<br>
                         Insert your API key in the onboarding wizard.""",
                "cta_text": self.ONBOARDING_CTA_TEXT,
                "cta_action": f"open-modal:{self.ONBOARDING_MODAL_PATH}",
                "dismissible": False,
                "source": "backend",
                # For programmatic clients (e.g. chat composer) reusing this banner pipeline
                "missing_providers": missing_providers,
            })
