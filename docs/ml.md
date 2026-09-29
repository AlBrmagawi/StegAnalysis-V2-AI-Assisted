# Experimental image baseline

No weights are shipped or enabled by default. The UI and Deep analyzer report **model not available** until the analyst explicitly configures an evaluated JSON artifact. This is a runnable experiment with real training, evaluation and inference, not a random score generator.

## Reproduce the bounded synthetic experiment

```sh
uv run --group ml steganalysis ml dataset --output ml-output/dataset --seed 1729
uv run --group ml steganalysis ml train --manifest ml-output/dataset/manifest.json --output ml-output/model.json
uv run --group ml steganalysis ml predict --model ml-output/model.json --image demo-fixtures/clean-landscape.png
```

Sixty generated original sources are assigned to train/validation/test (60/20/20) **before** variants are created. Each source yields a clean control, JPEG-quality-75 negative, and random-position LSB-replacement variants at 0.1, 0.4 and 1.0 bits per RGB channel value. All derivatives remain in the source group. These mathematical textures, including noisy controls, are **not natural photographs**.

The manifest records seed, source identity, split, payload setting, method, file hashes, composition and provenance. Training rejects cross-split source/hash duplication, tampered files, path escape, unknown labels and missing positive/negative classes. At most 300 user sources / 2,000 records are supported.

## Permissioned natural-source evaluation

Supply your own clean photographic source directory and record its permission/license. Include noisy camera images and varied image processing chains; JPEG negatives are generated for each source. Near-duplicates with different byte hashes are not automatically detected: curate related originals into independent groups before using this simple manifest generator.

```sh
uv run --group ml steganalysis ml dataset --sources /path/to/permissioned/photos --license-note "My original photographs; permission recorded in case XYZ" --output ml-output/natural
uv run --group ml steganalysis ml train --manifest ml-output/natural/manifest.json --output ml-output/natural-model.json
```

The baseline extracts 18 features from the top-left at most 256×256 decoded RGB crop: LSB fraction, horizontal bit transitions, adjacent-bin imbalance, median-filter residual mean/std, and neighbor differences per channel. No resize, DCT extraction or neural network is involved. StandardScaler fits **training data only**. A seeded balanced logistic regression is fitted on training data. The decision threshold is selected among 0.35/0.5/0.65 by validation F1; the test set is not used for fitting or threshold selection. This F1 objective can tolerate an unacceptable false-positive rate, so always inspect all metrics.

Weights, scaling, model/feature versions, dependency version, manifest hash, seed, composition, threshold and evaluation are serialized as bounded plain JSON. Inference uses NumPy and never loads pickle/joblib. Set `STEG_ML_MODEL` to an absolute JSON model path before starting the server to enable Deep inference. Scores remain a separate experimental finding category.

## Actual recorded synthetic result

Seed 1729, 60 sources / 300 records, 180 train / 60 validation / 60 test, scikit-learn 1.9.1:

| Split | Precision | Recall | F1 | ROC-AUC | False-positive rate |
|---|---:|---:|---:|---:|---:|
| Validation | 0.6122 | 0.8333 | 0.7059 | 0.6123 | 0.7917 |
| Held-out test sources | 0.6182 | 0.9444 | 0.7473 | 0.6204 | 0.8750 |

Test ROC-AUC by payload: 0.1 → 0.4931; 0.4 → 0.6181; 1.0 → 0.7500. Each comparison includes the same clean held-out controls. Negative-control false-positive rates: JPEG 0.8333, synthetic noise 0.8333, synthetic smooth 1.0. [Machine-readable evaluation](ml-evaluation.json) preserves the experiment metadata.

**These results are inadequate for operational detection.** They are reported rather than hidden. No accuracy on natural or unseen embedding methods is claimed. The high false-positive rate is a reason to leave the model unavailable by default and gather credible, independent data. Logistic scores are not calibrated probabilities of concealed content, and are never blended with heuristic results or assistant prose.

The protocol follows the [scikit-learn guidance on preprocessing and leakage](https://scikit-learn.org/stable/common_pitfalls.html). A valid source split reduces leakage; it does not cure domain shift or weak features.
