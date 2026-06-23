import os
import sys


sys.path.insert(0, os.path.abspath("../../.."))  # Adds the parent directory to the system path

from litellm.proxy.guardrails.init_guardrails import InitializeGuardrails
from litellm.types.guardrails import SupportedGuardrailIntegrations


def test_initialize_presidio_guardrail():
    """
    Test that initialize_guardrail correctly uses registered initializers
    for presidio guardrail
    """
    # Setup test data for a non-custom guardrail (using Presidio as an example)
    test_guardrail = {
        "guardrail_name": "test_presidio_guardrail",
        "litellm_params": {
            "guardrail": SupportedGuardrailIntegrations.PRESIDIO.value,
            "mode": "pre_call",
            "presidio_analyzer_api_base": "https://fakelink.com/v1/presidio/analyze",
            "presidio_anonymizer_api_base": "https://fakelink.com/v1/presidio/anonymize",
        },
    }

    # Ensure required environment variables are present for Presidio initializer
    import os

    os.environ["PRESIDIO_ANALYZER_API_BASE"] = test_guardrail["litellm_params"]["presidio_analyzer_api_base"]
    os.environ["PRESIDIO_ANONYMIZER_API_BASE"] = test_guardrail["litellm_params"]["presidio_anonymizer_api_base"]

    try:
        # Call the initialize_guardrail method
        result = InitializeGuardrails.initialize_guardrail(
            guardrail=test_guardrail,
        )

        assert result["guardrail_name"] == "test_presidio_guardrail"
        assert result["litellm_params"].guardrail == SupportedGuardrailIntegrations.PRESIDIO.value
        assert result["litellm_params"].mode == "pre_call"
    finally:
        # Clean up environment to avoid side effects for other tests
        os.environ.pop("PRESIDIO_ANALYZER_API_BASE", None)
        os.environ.pop("PRESIDIO_ANONYMIZER_API_BASE", None)
