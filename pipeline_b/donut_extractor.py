import torch
from transformers import DonutProcessor, VisionEncoderDecoderModel
from PIL import Image
import json
import logging

logger = logging.getLogger(__name__)

class DonutInvoiceExtractor:
    def __init__(self, model_name="naver-clova-ix/donut-base-finetuned-cord-v2"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(f"Loading Donut model on {self.device}")

        self.processor = DonutProcessor.from_pretrained(model_name)
        self.model = VisionEncoderDecoderModel.from_pretrained(model_name)
        self.model.to(self.device)

    def extract(self, image_path: str) -> dict:
        try:
            image = Image.open(image_path).convert("RGB")

            # Prompt for structured extraction
            task_prompt = (
                "<s_invoice>"
                "Extract the following fields as JSON: "
                "seller_name, seller_tax_id, client_name, client_tax_id, "
                "invoice_number, invoice_date, net_worth, vat, gross_worth."
                "</s_invoice>"
            )

            inputs = self.processor(
                image,
                task_prompt,
                return_tensors="pt"
            ).to(self.device)

            outputs = self.model.generate(
                **inputs,
                max_length=512,
                early_stopping=True
            )

            result = self.processor.decode(outputs[0], skip_special_tokens=True)

            # Clean up string
            result = result.strip()

            # Attempt JSON parsing
            parsed = self._safe_json_parse(result)

            logger.info("parsed: %s", parsed)

            return parsed

        except Exception as e:
            logger.error(f"Donut extraction failed for {image_path}: {e}")
            return self._empty_response()

    def _safe_json_parse(self, text: str) -> dict:
        try:
            return json.loads(text)
        except:
            logger.warning("Donut output is not valid JSON. Returning empty fields.")
            return self._empty_response()

    def _empty_response(self):
        return {
            "seller_name": None,
            "seller_tax_id": None,
            "client_name": None,
            "client_tax_id": None,
            "invoice_number": None,
            "invoice_date": None,
            "net_worth": None,
            "vat": None,
            "gross_worth": None,
        }