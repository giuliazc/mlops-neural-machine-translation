import json
import logging
from pathlib import Path
from typing import Any, Tuple

logger = logging.getLogger(__name__)


class ModelValidator:
    """
    Applies the Quality Gate for a given training run.
    O deploy so pode acontecer quando:
    - O diretorio saved_model existe.
    - O arquivo de metadata existe.
    - A metrica alvo existe.
    - A metrica alvo e maior ou igual ao threshold configurado.
    """
    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)

    @staticmethod
    def _target_metric(metadata: dict[str, Any]) -> str:
        metric_name = metadata.get("metric_name")
        return metric_name if isinstance(metric_name, str) and metric_name else "val_token_accuracy"

    @staticmethod
    def _metric_value(metadata: dict[str, Any], metric_name: str) -> float | None:
        direct_value = metadata.get("metric_value")
        if direct_value is not None and metadata.get("metric_name", metric_name) == metric_name:
            return float(direct_value)

        metrics = metadata.get("metrics", {})
        if isinstance(metrics, dict) and metrics.get(metric_name) is not None:
            return float(metrics[metric_name])

        legacy_value = metadata.get(metric_name)
        if legacy_value is not None:
            return float(legacy_value)

        return None

    def validate(self) -> Tuple[bool, str]:
        """
        Validates the run artifacts.
        Returns:
            (is_approved, reason)
        """
        saved_model_dir = self.run_dir / "saved_model"
        if not saved_model_dir.exists() or not saved_model_dir.is_dir():
            return False, "Diretorio saved_model nao encontrado."

        metadata_file = self.run_dir / "metadata.json"
        if not metadata_file.exists():
            return False, "Arquivo metadata.json nao encontrado."

        try:
            with metadata_file.open("r", encoding="utf-8") as f:
                metadata = json.load(f)
        except json.JSONDecodeError:
            return False, "Arquivo metadata.json invalido."

        metric_name = self._target_metric(metadata)
        try:
            metric_value = self._metric_value(metadata, metric_name)
            threshold = float(metadata.get("threshold", 0.30))
        except (TypeError, ValueError):
            return False, "Metadata contem metrica ou threshold invalido."

        if metric_value is None:
            return False, f"Metrica alvo ({metric_name}) nao encontrada."

        if metric_value < threshold:
            return False, f"Metrica {metric_value} abaixo do threshold {threshold}."

        if metadata.get("status") != "approved":
            return False, f"Status no metadata nao e 'approved' (encontrado: {metadata.get('status')})."

        return True, "Aprovado"


if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Model Quality Gate")
    parser.add_argument(
        "--run_dir",
        required=True,
        type=Path,
        help="Directory containing the model run artifacts (saved_model and metadata.json)",
    )
    args = parser.parse_args()
    
    validator = ModelValidator(args.run_dir)
    is_approved, reason = validator.validate()
    
    if is_approved:
        logger.info("Model validated successfully: %s", reason)
        print(f"APPROVED: {reason}")
        sys.exit(0)
    else:
        logger.error("Model validation failed: %s", reason)
        print(f"REJECTED: {reason}")
        sys.exit(1)
