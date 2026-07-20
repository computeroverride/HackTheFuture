from __future__ import annotations

import argparse
import random
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets

from app.ml.model import (
    IMAGE_SIZE,
    build_model,
    get_eval_transform,
    get_train_transform,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATA_DIR = (
    PROJECT_ROOT
    / "storage"
    / "datasets"
)

DEFAULT_MODEL_PATH = (
    PROJECT_ROOT
    / "storage"
    / "models"
    / "pill_classifier.pt"
)

EXPECTED_CLASSES = {
    "pass",
    "fail_different",
    "fail_defect",
}


class ImageSubset(Dataset):
    """
    Allows the training and validation subsets to use different transforms.
    """

    def __init__(
        self,
        base_dataset: datasets.ImageFolder,
        indices: list[int],
        transform,
    ):
        self.base_dataset = base_dataset
        self.indices = indices
        self.transform = transform

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, item: int):
        sample_index = self.indices[item]
        image_path, target = self.base_dataset.samples[sample_index]

        image = self.base_dataset.loader(image_path)
        image = self.transform(image)

        return image, target


def make_stratified_split(
    targets: list[int],
    val_ratio: float,
    seed: int,
) -> tuple[list[int], list[int]]:
    """
    Split each class separately so every class appears in training
    and validation.
    """

    if not 0.0 < val_ratio < 1.0:
        raise ValueError("val_ratio must be between 0 and 1")

    random_generator = random.Random(seed)

    train_indices: list[int] = []
    validation_indices: list[int] = []

    for class_id in sorted(set(targets)):
        class_indices = [
            index
            for index, target in enumerate(targets)
            if target == class_id
        ]

        if len(class_indices) < 2:
            raise ValueError(
                f"Class index {class_id} has only "
                f"{len(class_indices)} image(s). "
                "Each class needs at least two images."
            )

        random_generator.shuffle(class_indices)

        validation_count = max(
            1,
            round(len(class_indices) * val_ratio),
        )

        validation_count = min(
            validation_count,
            len(class_indices) - 1,
        )

        validation_indices.extend(
            class_indices[:validation_count]
        )

        train_indices.extend(
            class_indices[validation_count:]
        )

    random_generator.shuffle(train_indices)
    random_generator.shuffle(validation_indices)

    return train_indices, validation_indices


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
) -> tuple[float, float]:
    """
    Run either one training epoch or one validation epoch.

    optimizer provided: training
    optimizer omitted: validation
    """

    is_training = optimizer is not None
    model.train(is_training)

    total_loss = 0.0
    total_correct = 0
    total_samples = 0

    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        if is_training:
            optimizer.zero_grad(set_to_none=True)

        with torch.set_grad_enabled(is_training):
            logits = model(images)
            loss = criterion(logits, labels)

            if is_training:
                loss.backward()
                optimizer.step()

        batch_size = labels.size(0)

        total_loss += loss.item() * batch_size
        total_correct += (
            logits.argmax(dim=1) == labels
        ).sum().item()

        total_samples += batch_size

    average_loss = total_loss / total_samples
    accuracy = total_correct / total_samples

    return average_loss, accuracy


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the pill image classifier"
    )

    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_DIR,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MODEL_PATH,
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
    )

    parser.add_argument(
        "--learning-rate",
        type=float,
        default=3e-4,
    )

    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.20,
    )

    parser.add_argument(
        "--patience",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    torch.manual_seed(args.seed)
    random.seed(args.seed)

    if not args.data.exists():
        raise FileNotFoundError(
            f"Training folder not found: {args.data}"
        )

    base_dataset = datasets.ImageFolder(args.data)

    found_classes = set(base_dataset.classes)

    if found_classes != EXPECTED_CLASSES:
        raise ValueError(
            "Expected these class folders:\n"
            f"{sorted(EXPECTED_CLASSES)}\n\n"
            "Found these folders:\n"
            f"{sorted(found_classes)}"
        )

    train_indices, validation_indices = make_stratified_split(
        base_dataset.targets,
        args.val_ratio,
        args.seed,
    )

    train_dataset = ImageSubset(
        base_dataset,
        train_indices,
        get_train_transform(),
    )

    validation_dataset = ImageSubset(
        base_dataset,
        validation_indices,
        get_eval_transform(),
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )

    validation_loader = DataLoader(
        validation_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    model = build_model(
        num_classes=len(base_dataset.classes),
        pretrained=True,
    ).to(device)

    criterion = nn.CrossEntropyLoss()

    optimizer = torch.optim.AdamW(
        (
            parameter
            for parameter in model.parameters()
            if parameter.requires_grad
        ),
        lr=args.learning_rate,
        weight_decay=1e-4,
    )

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=0.5,
        patience=2,
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    best_validation_accuracy = -1.0
    epochs_without_improvement = 0

    print(f"Device: {device}")
    print(f"Classes: {base_dataset.classes}")
    print(f"Training images: {len(train_dataset)}")
    print(
        f"Validation images: "
        f"{len(validation_dataset)}"
    )

    for epoch in range(1, args.epochs + 1):
        train_loss, train_accuracy = run_epoch(
            model,
            train_loader,
            criterion,
            device,
            optimizer,
        )

        validation_loss, validation_accuracy = run_epoch(
            model,
            validation_loader,
            criterion,
            device,
        )

        scheduler.step(validation_accuracy)

        print(
            f"Epoch {epoch:02d}/{args.epochs} | "
            f"train loss {train_loss:.4f} | "
            f"train acc {train_accuracy:.2%} | "
            f"val loss {validation_loss:.4f} | "
            f"val acc {validation_accuracy:.2%}"
        )

        if validation_accuracy > best_validation_accuracy:
            best_validation_accuracy = validation_accuracy
            epochs_without_improvement = 0

            checkpoint = {
                "architecture": "efficientnet_b0",
                "image_size": IMAGE_SIZE,
                "class_names": base_dataset.classes,
                "model_state_dict": model.state_dict(),
                "best_val_accuracy": best_validation_accuracy,
            }

            torch.save(checkpoint, args.output)

            print(
                "  Saved new best model to: "
                f"{args.output}"
            )

        else:
            epochs_without_improvement += 1

            if (
                epochs_without_improvement
                >= args.patience
            ):
                print(
                    "Early stopping: validation "
                    "accuracy stopped improving."
                )
                break

    print(
        "Best validation accuracy: "
        f"{best_validation_accuracy:.2%}"
    )


if __name__ == "__main__":
    main()