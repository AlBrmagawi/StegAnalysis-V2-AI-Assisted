# Analysis methods and interpretation

## Profiles

Quick runs identity/strings/entropy and the native analyzer for the detected format. Images receive validated previews, histograms, bounded LSB statistics and demo framing checks, but no full transformation set. PDF extraction still runs and recursively inspects supported extracted content within budgets.

Standard adds image channels, bit planes 0/1/7, grayscale, negative and a median residual visualization. Deep adds all eight planes, optional external adapters and optional experimental ML inference. Absence of optional dependencies produces explicit skipped records. Unsupported signatures still receive byte inspection and a format-capability unsupported record.

## PDFs

pypdf parses metadata, pages, text, images and attachments. Page and object IDs are saved when exposed; text extraction `None` becomes an empty string with an explicit no-text observation. Image output extensions follow detected returned encoding. PDF image streams may be re-encoded by the parser; their extracted hashes are not claimed to identify a contiguous PDF byte slice.

A small version-pinned parser subclass retains `/Prev` links from parsed trailers and cross-reference streams before pypdf merges them. Tests include normal incremental updates. Trailing-byte inspection happens after parsing and uses only the final lexical `%%EOF` marker; earlier revision markers are not treated as concealed content. This is a limited structural observation, not a complete validation of all PDF grammar.

Encrypted PDFs with a nonempty required password are unsupported. No OCR, visual page renderer, JavaScript execution or password recovery is provided. Malformed documents are recorded as failures. Parser resource limits can retain partial outputs.

## Images

PNG/JPEG/BMP are decoded with Pillow after signature and pixel-limit checks. Modes 1, L, LA, P, RGB, RGBA and CMYK are handled deliberately by normalization to RGB/RGBA. Palette transparency and alpha are preserved in normalized previews. Channel/bit-plane calculations operate on the normalized representation, so palette indices and CMYK channels are not analyzed as original sample channels. 16-bit PNG and unhandled pixel modes report unsupported. EXIF orientation is not applied: locations and comparisons refer to stored decoded pixel order.

The chi-square statistic compares each adjacent `(2k, 2k+1)` intensity pair against equal expected counts. Pairs with fewer than ten total observations are excluded (expected count at least five per bin). Degrees of freedom equal the number of eligible pairs. The reported p-value tests that restricted null model; spatial dependencies and first-N sampling limit its interpretation. **It is not the probability of hidden content.** Sensor noise, dithering and image processing can explain LSB patterns. No heuristic is promoted to an automatic steganography verdict.

JPEG inspection is decoded-pixel inspection only. No DCT coefficient steganalysis, F5, JSteg or universal JPEG detector is implemented. The native residual is the absolute grayscale difference from a 3×3 median filter, amplified by 8 and clipped to 8-bit.

## Audio and text

WAV supports uncompressed integer PCM 8/16/24/32-bit and 1–8 channels. Sample-level statistics use decoded interleaved sample values, not container bytes. Waveform envelopes and STFT spectrograms are bounded to inspected frames. Spectrograms use a 512-sample window (or fewer for short clips), half overlap, and a fixed −100 to 0 dB visualization. Channel averaging can cancel out-of-phase signals. A raster shows the first 65,536 sample LSB values in rows of 256. Float/compressed WAV is unsupported; malformed containers fail explicitly.

Text analysis accepts UTF-8, reports format/invisible characters and unusual whitespace with 0-based Unicode/UTF-8 positions and 1-based lines/columns. PDF text byte offsets refer to the extracted UTF-8 artifact, not the source PDF. Typography, bidirectional writing, indentation and PDF layout are explicit alternative explanations.

## Verified demonstration recovery

The only native payload decoder recognizes `SADEMO1` + 4-byte big-endian length + payload + 4-byte big-endian CRC-32, packed MSB-first from sequential RGB channel LSBs or interleaved PCM sample LSBs. It inspects at most one million values and caps the payload at 65,536 bytes. CRC verifies the frame consistency, not authenticity. It does not claim to decode arbitrary real-world schemes.

## External adapters

| Tool | Invocation | Status without dependency |
|---|---|---|
| Binwalk | `binwalk <absolute-artifact-path>`; no `-e` | Skipped |
| zsteg | `zsteg <absolute-artifact-path>` for PNG/BMP | Skipped; JPEG unsupported |
| Steghide | `steghide info <absolute-artifact-path> -p ""`, closed stdin | Skipped; unavailable passphrases never guessed |
| Foremost | Not integrated; parser-based PDF extraction used | Explicitly unavailable |
| Stegsolve | Replaced by native web channels/planes/residuals | No JAR needed |

Tool versions, exact argument arrays, bounded stdout/stderr, truncation flags, exit status and elapsed time are persisted. A nonzero exit is a failed run, even if a tool’s wording appears reassuring. No tool is auto-installed. Unsupported versions may fail honestly; adapters should be validated against the versions installed by the analyst.
