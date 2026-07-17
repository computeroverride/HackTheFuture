from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import cv2
import torch
from PIL import Image

from app.ml.model import (
    build_model,
    get_eval_transform,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MODEL_PATH = (
    PROJECT_ROOT
    / "storage"
    / "models"
    / "pill_classifier.pt"
)

DEFAULT_TEST_DIR = (
    PROJECT_ROOT
    / "storage"
    / "test"
)

DEFAULT_RESULTS_CSV = (
    PROJECT_ROOT
    / "storage"
    / "predictions"
    / "test_results.csv"
)

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp",
}


def load_checkpoint(
    path: Path,
    device: torch.device,
) -> dict[str, Any]:
    """
    Supports both newer and older PyTorch versions.
    """

    try:
        return torch.load(
            path,
            map_location=device,
            weights_only=True,
        )
    except TypeError:
        return torch.load(
            path,
            map_location=device,
        )


class PillPredictor:
    def __init__(
        self,
        model_path: Path | str,
        min_confidence: float = 0.60,
    ):
        self.model_path = Path(model_path)
        self.min_confidence = min_confidence

        self.device = torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model not found: {self.model_path}"
            )

        checkpoint = load_checkpoint(
            self.model_path,
            self.device,
        )

        self.class_names: list[str] = checkpoint[
            "class_names"
        ]

        self.model = build_model(
            num_classes=len(self.class_names),
            pretrained=False,
            fine_tune_last_blocks=0,
        ).to(self.device)

        self.model.load_state_dict(
            checkpoint["model_state_dict"]
        )

        self.model.eval()
        self.transform = get_eval_transform()

    @torch.inference_mode()
    def predict_pil(
        self,
        image: Image.Image,
    ) -> dict[str, Any]:
        rgb_image = image.convert("RGB")

        tensor = (
            self.transform(rgb_image)
            .unsqueeze(0)
            .to(self.device)
        )

        logits = self.model(tensor)

        probabilities_tensor = torch.softmax(
            logits,
            dim=1,
        )[0]

        confidence, class_index = (
            probabilities_tensor.max(dim=0)
        )

        raw_label = self.class_names[
            class_index.item()
        ]

        confidence_value = confidence.item()

        probabilities = {
            class_name: probabilities_tensor[
                index
            ].item()
            for index, class_name
            in enumerate(self.class_names)
        }

        # Fail-safe behaviour:
        # an uncertain result is not allowed to pass.
        if confidence_value < self.min_confidence:
            final_label = "fail_uncertain"
            is_pass = False
        else:
            final_label = raw_label
            is_pass = raw_label == "pass"

        return {
            "raw_label": raw_label,
            "final_label": final_label,
            "confidence": confidence_value,
            "is_pass": is_pass,
            "probabilities": probabilities,
        }

    def predict_path(
        self,
        image_path: Path | str,
    ) -> dict[str, Any]:
        with Image.open(image_path) as image:
            return self.predict_pil(image)

    def predict_frame(
        self,
        bgr_frame,
    ) -> dict[str, Any]:
        """
        Used later by the webcam service.
        """

        rgb_frame = cv2.cvtColor(
            bgr_frame,
            cv2.COLOR_BGR2RGB,
        )

        pil_image = Image.fromarray(rgb_frame)

        return self.predict_pil(pil_image)


def test_folder(
    predictor: PillPredictor,
    folder: Path,
    output_csv: Path,
) -> None:
    image_paths = sorted(
        path
        for path in folder.rglob("*")
        if (
            path.is_file()
            and path.suffix.lower()
            in SUPPORTED_EXTENSIONS
        )
    )

    if not image_paths:
        raise ValueError(
            f"No supported images found in: {folder}"
        )

    rows: list[dict[str, Any]] = []

    for image_path in image_paths:
        result = predictor.predict_path(image_path)

        row: dict[str, Any] = {
            "file": str(image_path),
            "raw_label": result["raw_label"],
            "final_label": result["final_label"],
            "confidence": (
                f'{result["confidence"]:.4f}'
            ),
            "is_pass": result["is_pass"],
        }

        row.update(
            {
                f"prob_{class_name}": (
                    f"{probability:.4f}"
                )
                for class_name, probability
                in result["probabilities"].items()
            }
        )

        rows.append(row)

        print(
            f"{image_path.name}: "
            f"{result['final_label']} "
            f"({result['confidence']:.1%})"
        )

    output_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_csv.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0].keys()),
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved results to: {output_csv}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run pill classification"
    )

    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
    )

    parser.add_argument(
        "--confidence",
        type=float,
        default=0.60,
    )

    source = parser.add_mutually_exclusive_group()

    source.add_argument(
        "--image",
        type=Path,
    )

    source.add_argument(
        "--folder",
        type=Path,
        default=DEFAULT_TEST_DIR,
    )

    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_RESULTS_CSV,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    predictor = PillPredictor(
        args.model,
        min_confidence=args.confidence,
    )

    if args.image is not None:
        result = predictor.predict_path(args.image)
        print(result)
    else:
        test_folder(
            predictor,
            args.folder,
            args.output_csv,
        )


if __name__ == "__main__":
    main()