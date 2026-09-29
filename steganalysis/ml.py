"""Experimental sequential/random LSB-replacement baseline. No universal steganalysis claim."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from .storage import contained

FEATURE_VERSION = "rgb-residual-lsb-v1"
FEATURE_NAMES = [
    f"{c}_{f}"
    for c in "RGB"
    for f in (
        "lsb_mean",
        "lsb_horizontal_transition",
        "pair_imbalance",
        "residual_mean",
        "residual_std",
        "neighbor_difference",
    )
]


def features(image: Image.Image) -> np.ndarray:
    if image.width * image.height > 12_000_000:
        raise ValueError("Image exceeds 12 million pixels")
    # Crop bounds compute; no resize that would erase the signal under examination.
    rgb = image.convert("RGB").crop((0, 0, min(image.width, 256), min(image.height, 256)))
    if min(rgb.size) < 8:
        raise ValueError("Image must be at least 8×8")
    pixels = np.asarray(rgb, dtype=np.int16)
    median = np.asarray(rgb.filter(ImageFilter.MedianFilter(3)), dtype=np.int16)
    output = []
    for i in range(3):
        channel = pixels[:, :, i]
        bits = channel & 1
        hist = np.bincount(channel.ravel(), minlength=256).reshape(128, 2)
        residual = (channel - median[:, :, i]).astype(float)
        output.extend(
            [
                float(bits.mean()),
                float((bits[:, 1:] != bits[:, :-1]).mean()),
                float(np.abs(hist[:, 0] - hist[:, 1]).sum() / channel.size),
                float(np.abs(residual).mean()),
                float(residual.std()),
                float(np.abs(np.diff(channel, axis=1)).mean()),
            ]
        )
    return np.array(output, dtype=float)


def build_dataset(
    output: Path, sources: Path | None = None, seed: int = 1729, count: int = 60, license_note: str = ""
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    inputs: list[tuple[str, Image.Image, str]] = []
    if sources:
        if not license_note:
            raise ValueError("For user-supplied images, record permission/license using --license-note")
        for path in sorted(sources.iterdir()):
            if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".bmp") or path.is_symlink():
                continue
            if path.stat().st_size > 32 * 1024 * 1024:
                raise ValueError("Source exceeds 32 MiB")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if any(item[0] == digest for item in inputs):
                continue
            with Image.open(path) as im:
                if im.width * im.height > 12_000_000:
                    raise ValueError("Source exceeds decoded pixel budget")
                inputs.append(
                    (
                        digest,
                        im.convert("RGB").crop((0, 0, min(im.width, 256), min(im.height, 256))),
                        "user-supplied",
                    )
                )
            if len(inputs) >= 300:
                break
    else:
        for i in range(count):
            yy, xx = np.mgrid[:128, :128]
            phase = rng.uniform(0, 6.28, 3)
            image = np.stack(
                [
                    110 + 40 * np.sin(xx / rng.uniform(5, 30) + p) + 30 * np.cos(yy / rng.uniform(5, 30) + p)
                    for p in phase
                ],
                axis=-1,
            )
            image += rng.normal(0, [1, 6, 20, 45][i % 4], image.shape)
            values = image.clip(0, 255).astype(np.uint8)
            inputs.append(
                (
                    hashlib.sha256(values.tobytes()).hexdigest(),
                    Image.fromarray(values),
                    "synthetic-noise" if i % 4 > 1 else "synthetic-smooth",
                )
            )
    if len(inputs) < 12:
        raise ValueError("Need at least 12 distinct original sources for source-separated splits")
    order = rng.permutation(len(inputs))
    groups = {
        int(index): "train"
        if rank < int(len(inputs) * 0.6)
        else "validation"
        if rank < int(len(inputs) * 0.8)
        else "test"
        for rank, index in enumerate(order)
    }
    records = []
    for i, (source_hash, original, control) in enumerate(inputs):
        # Assign split BEFORE any derivative/embedding. Every derivative stays with its source.
        variants: list[tuple[Image.Image, int, float, str]] = [(original, 0, 0, control)]
        jpeg = io.BytesIO()
        original.save(jpeg, format="JPEG", quality=75)
        with Image.open(io.BytesIO(jpeg.getvalue())) as compressed:
            variants.append((compressed.convert("RGB"), 0, 0, "JPEG-compressed negative"))
        for rate in (0.1, 0.4, 1.0):
            data = np.array(original)
            flat = data.ravel()
            indices = rng.choice(len(flat), int(len(flat) * rate), replace=False)
            flat[indices] = (flat[indices] & 254) | rng.integers(0, 2, len(indices), dtype=np.uint8)
            variants.append((Image.fromarray(data), 1, rate, "random-position LSB replacement"))
        for j, (variant_image, label, rate, method) in enumerate(variants):
            path = output / f"source-{i:04d}-variant-{j}.png"
            variant_image.save(path)
            records.append(
                {
                    "path": path.name,
                    "source_id": source_hash,
                    "split": groups[i],
                    "label": label,
                    "payload_rate": rate,
                    "method": method,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    manifest = {
        "seed": seed,
        "source_count": len(inputs),
        "feature_version": FEATURE_VERSION,
        "dataset_type": "user-supplied" if sources else "synthetic-only",
        "license_note": license_note
        or "Locally generated mathematical textures; no third-party image inputs",
        "records": records,
        "limitation": "Only this LSB-replacement experiment. Synthetic results do not establish accuracy on natural images.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_dataset(manifest_path: Path) -> tuple[dict, np.ndarray, np.ndarray]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    seen_groups: dict[str, str] = {}
    seen_hashes: dict[str, str] = {}
    rows, labels = [], []
    if len(manifest["records"]) > 2000:
        raise ValueError("Dataset exceeds the 2,000-record limit")
    for row in manifest["records"]:
        split = row["split"]
        if split not in ("train", "validation", "test"):
            raise ValueError("Unknown split")
        for key, seen in (("source_id", seen_groups), ("sha256", seen_hashes)):
            if row[key] in seen and seen[row[key]] != split:
                raise ValueError("Source/duplicate leakage between splits")
            seen[row[key]] = split
        path = contained(manifest_path.parent, row["path"])
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Invalid dataset path or size")
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Dataset hash mismatch")
        with Image.open(path) as image:
            rows.append(features(image))
        if row["label"] not in (0, 1):
            raise ValueError("Labels must be 0 or 1")
        labels.append(row["label"])
    return manifest, np.array(rows), np.array(labels)


def train(manifest_path: Path, output: Path) -> dict:
    import sklearn
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
    from sklearn.preprocessing import StandardScaler

    manifest, x, y = load_dataset(manifest_path)
    split = np.array([r["split"] for r in manifest["records"]])
    for name in ("train", "validation", "test"):
        if len(set(y[split == name])) < 2:
            raise ValueError(f"{name} must contain positive and negative examples")
    scaler = StandardScaler().fit(x[split == "train"])
    model = LogisticRegression(max_iter=1500, random_state=manifest["seed"], class_weight="balanced").fit(
        scaler.transform(x[split == "train"]), y[split == "train"]
    )
    scores = model.predict_proba(scaler.transform(x))[:, 1]
    validation = split == "validation"
    threshold = max((0.35, 0.5, 0.65), key=lambda t: f1_score(y[validation], scores[validation] >= t))

    def metrics(mask: np.ndarray) -> dict:
        actual, predicted = y[mask], (scores[mask] >= threshold).astype(int)
        return {
            "n": int(mask.sum()),
            "precision": float(precision_score(actual, predicted, zero_division=0)),
            "recall": float(recall_score(actual, predicted, zero_division=0)),
            "f1": float(f1_score(actual, predicted, zero_division=0)),
            "roc_auc": float(roc_auc_score(actual, scores[mask])) if len(set(actual)) == 2 else None,
            "false_positive_rate": float(predicted[actual == 0].mean()) if (actual == 0).any() else None,
        }

    evaluation = {name: metrics(split == name) for name in ("validation", "test")}
    rates = np.array([r["payload_rate"] for r in manifest["records"]])
    evaluation["held_out_payload_rates"] = {
        str(rate): metrics((split == "test") & ((rates == rate) | (y == 0))) for rate in (0.1, 0.4, 1.0)
    }
    evaluation["held_out_controls"] = {
        method: metrics(
            (split == "test") & (y == 0) & np.array([r["method"] == method for r in manifest["records"]])
        )
        for method in sorted({r["method"] for r in manifest["records"] if r["label"] == 0})
    }
    artifact = {
        "schema_version": 1,
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "model_version": "logistic-lsb-v1",
        "sklearn_version": sklearn.__version__,
        "seed": manifest["seed"],
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "dataset_type": manifest["dataset_type"],
        "source_count": manifest["source_count"],
        "composition": {name: int((split == name).sum()) for name in ("train", "validation", "test")},
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": model.coef_[0].tolist(),
        "intercept": float(model.intercept_[0]),
        "threshold": threshold,
        "evaluation": evaluation,
        "limitations": "Experimental logistic score, not calibrated hidden-data probability. Evaluated only on random-position RGB LSB replacement, top-left <=256×256 crop. No DCT analysis. Synthetic-only evaluation cannot substantiate field accuracy.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, allow_nan=False), encoding="utf-8")
    return artifact


def predict(image: Image.Image, model_path: Path) -> dict:
    if model_path.stat().st_size > 1024 * 1024:
        raise ValueError("Model JSON exceeds 1 MiB")
    raw = model_path.read_bytes()
    model = json.loads(raw)
    if model["feature_version"] != FEATURE_VERSION or model["feature_names"] != FEATURE_NAMES:
        raise ValueError("Unsupported model feature version")
    x = features(image)
    arrays = [np.array(model[k], dtype=float) for k in ("mean", "scale", "coef")]
    if any(a.shape != x.shape or not np.isfinite(a).all() for a in arrays) or (arrays[1] <= 0).any():
        raise ValueError("Invalid model coefficients")
    z = float(((x - arrays[0]) / arrays[1]) @ arrays[2] + model["intercept"])
    if not np.isfinite(z) or not 0 < model["threshold"] < 1:
        raise ValueError("Invalid model intercept/threshold")
    score = float(1 / (1 + np.exp(-np.clip(z, -700, 700))))
    return {
        "score": score,
        "threshold": model["threshold"],
        "experimental_label": "matches evaluated method"
        if score >= model["threshold"]
        else "below experimental threshold",
        "model_sha256": hashlib.sha256(raw).hexdigest(),
        "model_version": model["model_version"],
        "dataset_type": model["dataset_type"],
        "features": dict(zip(FEATURE_NAMES, x.tolist(), strict=True)),
        "evaluation": model["evaluation"],
        "limitations": model["limitations"],
    }


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("dataset")
    generate.add_argument("--output", type=Path, default=Path("ml-output/dataset"))
    generate.add_argument("--sources", type=Path)
    generate.add_argument("--license-note", default="")
    generate.add_argument("--seed", type=int, default=1729)
    fitting = commands.add_parser("train")
    fitting.add_argument("--manifest", type=Path, required=True)
    fitting.add_argument("--output", type=Path, default=Path("ml-output/model.json"))
    inference = commands.add_parser("predict")
    inference.add_argument("--model", type=Path, required=True)
    inference.add_argument("--image", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "dataset":
        result = build_dataset(args.output, args.sources, args.seed, license_note=args.license_note)
        print(json.dumps({k: v for k, v in result.items() if k != "records"}, indent=2))
    elif args.command == "train":
        print(json.dumps(train(args.manifest, args.output)["evaluation"], indent=2))
    else:
        with Image.open(args.image) as image:
            print(json.dumps(predict(image, args.model), indent=2))


if __name__ == "__main__":
    main()
