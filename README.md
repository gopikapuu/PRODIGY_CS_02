# 🔐 Pixel Image Encryptor

A dual-mode image encryption tool built with **Python** (CLI) and **HTML/CSS/JS** (Browser GUI) that encrypts and decrypts images using pixel-level manipulation — no external crypto libraries required.

---

## ✨ Features

- 🔒 **Encrypt** any image using 4 independent pixel manipulation methods
- 🔓 **Decrypt** perfectly — lossless round-trip guaranteed
- 🖥️ **Browser GUI** — drag & drop, live preview, one-click download
- 🐍 **Python CLI** — scriptable, importable, pipeline-friendly
- 🔑 **Key-based** — same key + same methods = same result every time
- 📦 **Zero external dependencies** for the browser tool

---

## 🧠 Encryption Methods

| Method | How It Works | Self-Inverse? |
|---|---|---|
| ⊕ **XOR Cipher** | XORs every R/G/B channel byte with `key % 256` | ✅ Yes |
| 🎨 **Channel Swap** | Shuffles R, G, B channels using a seeded permutation | ❌ (inverted on decrypt) |
| 🔀 **Pixel Shuffle** | Scrambles all pixel positions with a seeded random order | ❌ (reversed on decrypt) |
| ☀️ **Brightness Flip** | Inverts each channel value: `255 - value` | ✅ Yes |

> **Key insight:** Decryption applies all operations in **reverse order** with inverted logic — so combining multiple methods creates a cascade that makes the encrypted image look like pure noise.

---

## 🚀 Getting Started

### Browser GUI (No install needed)

1. Open `pixel_encryptor_gui.html` in any modern browser
2. Upload an image (drag & drop or click)
3. Toggle the encryption methods you want
4. Set your key using the slider (1–255)
5. Click **▲ Encrypt** or **▼ Decrypt**
6. Click **⬇ Download Result** to save

> Everything runs locally in your browser. No data leaves your device.

---

### Python CLI

#### Requirements

```bash
pip install Pillow numpy
```

#### Encrypt an image

```bash
python image_encryptor.py encrypt photo.jpg encrypted.png --key 1234
```

#### Decrypt an image

```bash
python image_encryptor.py decrypt encrypted.png restored.png --key 1234
```

#### Use specific methods

```bash
python image_encryptor.py encrypt photo.jpg out.png --key 99 --methods xor brightness
```

#### List all options

```bash
python image_encryptor.py --help
```

---

### Python API

```python
from image_encryptor import ImageEncryptor

enc = ImageEncryptor(key=1234, methods=['xor', 'channel', 'pixel'])

# Encrypt
enc.encrypt('photo.jpg', 'encrypted.png')

# Decrypt — pixel-perfect restoration guaranteed
enc.decrypt('encrypted.png', 'restored.png')
```

---

## 📁 Project Structure

```
pixel-image-encryptor/
├── image_encryptor.py        # Python CLI & API
├── pixel_encryptor_gui.html  # Standalone browser GUI
├── README.md                 # Project documentation
└── .gitignore
```

---

## 🖼️ Example

```
Original : photo.jpg       → clear, readable image
Encrypted: encrypted.png   → looks like random noise
Decrypted: restored.png    → identical to original ✅
```

Round-trip test (Python):

```python
from image_encryptor import ImageEncryptor
import numpy as np
from PIL import Image

enc = ImageEncryptor(key=42, methods=['xor', 'channel', 'pixel', 'brightness'])
enc.encrypt('input.png', 'encrypted.png')
enc.decrypt('encrypted.png', 'decrypted.png')

orig     = np.array(Image.open('input.png'))
restored = np.array(Image.open('decrypted.png'))
assert np.array_equal(orig, restored)  # ✅ Always passes
```

---

## ⚠️ Disclaimer

This tool is built for **educational purposes**. The Caesar Cipher and pixel-manipulation techniques demonstrated here are **not cryptographically secure** and should not be used for protecting sensitive real-world data. For production security, use established standards like AES-256.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 🙌 Author

Built as part of the **Prodigy InfoTech Cybersecurity Internship** — Task 02.

> GitHub: [github.com/your-username/PRODIGY_CS_02](https://github.com/your-username/PRODIGY_CS_02)
