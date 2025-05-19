import logging
from openai import AsyncOpenAI
from typing import List, Dict, Optional
import openai
import json

from app.core.config import settings
from app.core import prompts

logger = logging.getLogger(__name__)

if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "YOUR_DEFAULT_OPENAI_KEY" and (settings.OPENAI_API_KEY.startswith("sk-proj-") or settings.OPENAI_API_KEY.startswith("sk-")):
    logger.info("Initializing OpenAI client with key from settings.")
    ai_client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url="https://api.openai.com/v1"
    )
else:
    logger.warning(
        "OpenAI API key is not configured correctly in .env (expected as OPENAI_API_KEY) or is missing. "
        "AI services requiring OpenAI will not be functional."
    )
    ai_client = None

async_openai_client = openai.AsyncOpenAI(
    api_key=settings.deep_seek_api_key,
    base_url="https://api.deepseek.com/v1"
)

class AIService:
    async def generate_case_study(self, user_prompt: str = None) -> str:
        system_prompt = (
            "You are an AI assistant specialized in creating realistic and complex psychotherapeutic case studies. "
            "These case studies are for training psychotherapists. Ensure the cases are nuanced, present a clear problem, "
            "and provide enough detail for a therapist to begin formulating a hypothesis and treatment plan. "
            "The case should not include a solution or diagnosis, only the patient's presentation. "
            "Output ONLY the case study text, without any preambles like 'Here is a case study:' or similar."
        )
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        if user_prompt:
            messages.append({"role": "user", "content": f"Please generate a case study with the following focus: {user_prompt}"})
        else:
            messages.append({"role": "user", "content": "Please generate a new psychotherapeutic case study."})

        try:
            response = await async_openai_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.7, 
                max_tokens=3000
            )
            case_text = response.choices[0].message.content.strip()
            
            prefixes_to_remove = [
                "here is a case study for you:",
                "here is a case study:",
                "here's your case study:",
                "case study:",
                "okay, here's a case study:"
            ]
            for prefix in prefixes_to_remove:
                if case_text.lower().startswith(prefix):
                    case_text = case_text[len(prefix):].strip()
                    break 
            return case_text
        except Exception as e:
            print(f"Error generating case study from DeepSeek: {e}")
            return "Произошла ошибка при генерации кейса. Пожалуйста, попробуйте позже."

ai_service = AIService()

def format_references_for_prompt(references: List[Dict[str, str]]) -> str:
    if not references:
        return "No specific reference materials provided. Base your response on general knowledge if necessary, but prioritize official CBT guidelines if known."
    
    formatted_str = "Key Reference Materials to use EXCLUSIVELY:\\n\\n"
    for i, ref in enumerate(references):
        formatted_str += f"Source {i+1}:\\n"
        formatted_str += f"  Type: {ref.get('type', 'N/A')}\\n"
        formatted_str += f"  Description: {ref.get('description', 'N/A')}\\n"
        if ref.get('url'):
            formatted_str += f"  URL: {ref.get('url')}\\n"
        if ref.get('citation'):
            formatted_str += f"  Citation: {ref.get('citation')}\\n"
        formatted_str += "---\\n"
    return formatted_str

async def generate_text_with_ai(
    messages: List[Dict[str, str]],
    model: str, # Модель будет передаваться конкретная
    temperature: float = 0.7,
    max_tokens: int = 3000
) -> Optional[str]:
    if not ai_client:
        logger.error("AI client (OpenRouter) is not initialized. Check API key configuration.")
        return None

    try:

        response = await ai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False
        )
        
        generated_text = None
        if response.choices and response.choices[0].message:
            message_obj = response.choices[0].message
            if message_obj.content and message_obj.content.strip():
                generated_text = message_obj.content.strip()
            elif message_obj.reasoning and message_obj.reasoning.strip():
                reasoning_content = message_obj.reasoning.strip()
                json_start_index = reasoning_content.find("{")
                json_end_index = reasoning_content.rfind("}")
                if json_start_index != -1 and json_end_index != -1 and json_start_index < json_end_index:
                    potential_json = reasoning_content[json_start_index : json_end_index + 1]
                    if potential_json.startswith("{") and potential_json.endswith("}"):
                         generated_text = potential_json
                    else:
                        logger.warning(f"Could not reliably extract JSON from reasoning for model {model}. Using full reasoning. Reasoning: {reasoning_content[:200]}...")
                        generated_text = reasoning_content
                else:
                     logger.warning(f"Reasoning found for model {model} but no clear JSON object. Reasoning: {reasoning_content[:200]}...")

        if generated_text:
            return generated_text
        else:
            logger.warning(
                f"AI API (model: {model}) returned no choices, empty message, or no content in expected fields. "
                f"Response object: {response.model_dump_json(indent=2)}"
            )
            return None
    except Exception as e:
        logger.error(f"Error calling AI API (model: {model}): {e}", exc_info=True)
        return None

async def generate_case_from_ai(
    user_prompt_text: Optional[str] = None, 
    active_references: Optional[List[Dict[str, str]]] = None
) -> Optional[Dict[str, str]]:
    
    formatted_references = format_references_for_prompt(active_references)
    system_prompt = prompts.CASE_GENERATION_SYSTEM_PROMPT.format(formatted_references=formatted_references)
    current_user_prompt = user_prompt_text if user_prompt_text else prompts.CASE_GENERATION_USER_PROMPT
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": current_user_prompt}
    ]

    model_for_case_generation = "gpt-4o-mini"
    generated_content = await generate_text_with_ai(
        messages=messages, 
        model=model_for_case_generation, 
        temperature=0.8, 
        max_tokens=4000
    )

    if generated_content:
        try:
            import json
            content_to_parse = generated_content.strip()
            if content_to_parse.startswith("```json"):
                content_to_parse = content_to_parse[len("```json"):].strip()
            elif content_to_parse.startswith("```"):
                 content_to_parse = content_to_parse[len("```"):].strip()
            
            if content_to_parse.endswith("```"):
                content_to_parse = content_to_parse[:-len("```")]
            
            content_to_parse = content_to_parse.strip()
            
            case_data = json.loads(content_to_parse)
            if isinstance(case_data, dict) and "title" in case_data and "description" in case_data:
                return case_data
            else:
                logger.error(f"AI (model {model_for_case_generation}) returned malformed JSON for case: {generated_content}")
                return {"title": f"Кейс от {model_for_case_generation} (не удалось распарсить)", "description": generated_content}
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from AI (model {model_for_case_generation}) for case: {generated_content}", exc_info=True)
            return {"title": f"Кейс от {model_for_case_generation} (ошибка декодирования)", "description": generated_content}
    return None

async def analyze_solution_with_ai(
    case_description: str, 
    user_solution_text: str,
    active_references: Optional[List[Dict[str, str]]] = None
) -> Optional[Dict[str, str]]:
    
    formatted_references = format_references_for_prompt(active_references)
    system_prompt = prompts.SOLUTION_ANALYSIS_SYSTEM_PROMPT.format(formatted_references=formatted_references)
    user_content = prompts.SOLUTION_ANALYSIS_USER_PROMPT_TEMPLATE.format(
        case_description=case_description,
        user_solution_text=user_solution_text
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    model_for_analysis = "gpt-4o-mini"
    generated_analysis_json = await generate_text_with_ai(
        messages=messages, 
        model=model_for_analysis, 
        temperature=0.5, 
        max_tokens=3000
    )
    
    if generated_analysis_json:
        try:
            import json
            content_to_parse = generated_analysis_json.strip()
            if content_to_parse.startswith("```json"):
                content_to_parse = content_to_parse[len("```json"):].strip()
            if content_to_parse.endswith("```"):
                content_to_parse = content_to_parse[:-len("```")]
            content_to_parse = content_to_parse.strip()

            analysis_data = json.loads(content_to_parse)
            if isinstance(analysis_data, dict) and \
               "strengths" in analysis_data and \
               "areas_for_improvement" in analysis_data and \
               "overall_impression" in analysis_data and \
               "solution_rating" in analysis_data:
                return analysis_data
            else:
                logger.error(f"AI (model {model_for_analysis}) returned malformed JSON for solution analysis (missing expected keys): {generated_analysis_json}")
                return {"error": "Malformed JSON response from AI - missing keys", "raw_response": generated_analysis_json}
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from AI (model {model_for_analysis}) for solution analysis: {generated_analysis_json}", exc_info=True)
            return {"error": "JSONDecodeError from AI response", "raw_response": generated_analysis_json}
    return None

async def analyze_feedback_substance(feedback_text: str) -> Optional[Dict[str, any]]:

    system_prompt = prompts.FEEDBACK_ANALYSIS_SYSTEM_PROMPT
    user_prompt = prompts.FEEDBACK_ANALYSIS_USER_PROMPT_TEMPLATE.format(feedback_text=feedback_text)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    model_for_feedback_analysis = "gpt-4o-mini"
    
    logger.debug(f"Sending feedback to AI for analysis. Model: {model_for_feedback_analysis}. Feedback: '{feedback_text[:100]}...' ")

    raw_response = await generate_text_with_ai(
        messages=messages,
        model=model_for_feedback_analysis,
        temperature=0.3,
        max_tokens=1000
    )

    if raw_response:
        logger.debug(f"Raw AI response for feedback analysis: {raw_response}")
        try:
            import json
            content_to_parse = raw_response.strip()
            if content_to_parse.startswith("```json"):
                content_to_parse = content_to_parse[len("```json"):].strip()
            if content_to_parse.endswith("```"):
                content_to_parse = content_to_parse[:-len("```")]
            content_to_parse = content_to_parse.strip()
            
            if not (content_to_parse.startswith("{") and content_to_parse.endswith("}")):
                logger.error(f"AI response for feedback analysis is not a valid JSON object: {content_to_parse}")
                return {"is_meaningful": None, "reason": "AI response was not valid JSON.", "category": "error", "raw_response": raw_response}

            analysis_data = json.loads(content_to_parse)
            
            if isinstance(analysis_data, dict) and \
               isinstance(analysis_data.get("is_meaningful"), bool) and \
               isinstance(analysis_data.get("reason"), str) and \
               isinstance(analysis_data.get("category"), str):
                logger.info(f"Feedback analysis successful: is_meaningful={analysis_data['is_meaningful']}")
                return analysis_data
            else:
                logger.error(f"AI (model {model_for_feedback_analysis}) returned malformed or incomplete JSON for feedback analysis: {raw_response}")
                return {"is_meaningful": None, "reason": "Malformed or incomplete JSON response from AI.", "category": "error", "raw_response": raw_response}
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from AI (model {model_for_feedback_analysis}) for feedback analysis: {raw_response}", exc_info=True)
            return {"is_meaningful": None, "reason": "JSONDecodeError from AI response.", "category": "error", "raw_response": raw_response}
        except Exception as e:
            logger.error(f"Unexpected error during feedback analysis post-processing: {e}", exc_info=True)
            return {"is_meaningful": None, "reason": f"Unexpected error: {str(e)}", "category": "error", "raw_response": raw_response}

    logger.warning(f"No response from AI for feedback analysis (model: {model_for_feedback_analysis}).")
    return None 
