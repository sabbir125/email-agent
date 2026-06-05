import json
import logging
from openai import OpenAI, OpenAIError
from typing import Optional

from app.config import get_settings
from app.schemas.email import RawEmail, ClassificationResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI email classifier. Analyze the email and classify it.
You MUST respond with valid JSON only. No markdown, no explanation, no extra text.

The JSON response must have exactly these fields:
- "important": boolean (true if the email requires attention or action)
- "priority": one of "HIGH", "MEDIUM", "LOW"
- "category": one of "PAYMENT_ISSUE", "SERVER_DOWN", "CUSTOMER_COMPLAINT", "ACCOUNT_ACCESS", "GENERAL_SUPPORT", "NEWSLETTER", "SPAM"
- "confidence": integer from 0 to 100
- "reason": brief explanation string

Respond ONLY with the JSON object."""


def classify_email(email: RawEmail) -> Optional[ClassificationResult]:
    """Classify an email using OpenAI API.

    Args:
        email: The raw email to classify.

    Returns:
        ClassificationResult if successful, None if classification fails.
    """
    settings = get_settings()

    user_prompt = f"""Classify this email:
                From: {email.from_address}
                Subject: {email.subject}
                Body: {email.body}
                
                """

    try:
        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT,
        )

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=256,
        )

        content = response.choices[0].message.content
        if not content:
            logger.error(f"Empty response from OpenAI for email {email.id}")
            return None

        # Strip potential markdown fencing
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0]
            content = content.strip()

        parsed = json.loads(content)
        result = ClassificationResult.model_validate(parsed)
        logger.info(f"Classified email {email.id}: {result.category} ({result.priority})")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from OpenAI for email {email.id}: {e}")
        return None
    except OpenAIError as e:
        logger.error(f"OpenAI API error for email {email.id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error classifying email {email.id}: {e}")
        return None
