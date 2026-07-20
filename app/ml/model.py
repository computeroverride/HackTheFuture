from __future__ import annotations

from torch import nn
from torchvision import transforms
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0


IMAGE_SIZE = 224

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_model(
    num_classes: int,
    *,
    pretrained: bool = True,
    fine_tune_last_blocks: int = 2,
) -> nn.Module:
    

    if num_classes < 2:
        raise ValueError("num_classes must be at least 2")

    weights = EfficientNet_B0_Weights.DEFAULT if pretrained else None
    model = efficientnet_b0(weights=weights)

    input_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(input_features, num_classes)

    # Freeze the main feature extractor.
    for parameter in model.features.parameters():
        parameter.requires_grad = False

    # Fine-tune only the final blocks.
    if fine_tune_last_blocks > 0:
        for block in model.features[-fine_tune_last_blocks:]:
            for parameter in block.parameters():
                parameter.requires_grad = True

    return model


def get_train_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),

            # Keeps position/orientation variation,
            # but does not change the pill colour.
            transforms.RandomRotation(degrees=8),

            transforms.ToTensor(),

            transforms.Normalize(
                IMAGENET_MEAN,
                IMAGENET_STD,
            ),
        ]
    )

def get_eval_transform() -> transforms.Compose:
   

    return transforms.Compose(
        [
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )