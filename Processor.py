import fitz
import docx
import regex as re
from pathlib import Path
from doctr.models import ocr_predictor
from doctr.io import DocumentFile
import tempfile
import os


class TextProcess:
    def read_file(self, file):
        if isinstance(file, str) and "\n" in file:
            return file

        path = Path(file)

        if path.suffix.lower() == ".pdf":
            text = self.read_pdf(path)
            if len(text.strip()) < 100:
                print(f"-{path.name} — metin yetersiz, OCR deneniyor...")
                text = self.read_pdf_ocr(path)
            return text
        elif path.suffix.lower() == ".docx":
            return self.read_docx(path)
        elif path.suffix.lower() in [".txt", ".json"]:
            return path.read_text(encoding="utf-8")
        else:
            raise ValueError("desteklenmeyen dosya türü: " + path.suffix)

    def read_pdf(self, path):
        doc = fitz.open(path)
        return "\n".join(p.get_text("text", sort=True) for p in doc)

    def read_docx(self, path):
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs)

    def read_pdf_ocr(self, path):
        doc = fitz.open(path)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            doc.save(tmp_path)
            model  = ocr_predictor(det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", pretrained=True)
            result = model(DocumentFile.from_pdf(tmp_path))
            lines  = []
            for page in result.pages:
                for block in page.blocks:
                    for line in block.lines:
                        words = [w for w in line.words if w.value.strip() and w.confidence >= 0.4]
                        if words:
                            lines.append(" ".join(w.value for w in words))
            return "\n".join(lines)
        except Exception as e:
            print(f"HATA: {e}")
            return ""
        finally:
            doc.close()
            os.unlink(tmp_path)
    
    # -metin işleme

    def turkish_lower(self, text: str) -> str:
        return text.replace('İ', 'i').replace('I', 'ı').lower()

    def fix_turkish(self, text: str) -> str:
        mapping = {
            r'G\s*˘|˘\s*G': 'Ğ', r'g\s*˘|˘\s*g': 'ğ',
            r'C\s*¸|¸\s*C': 'Ç', r'c\s*¸|¸\s*c': 'ç',
            r'˙\s*I|I\s*˙': 'İ', r'˙\s*ı|ı\s*˙': 'i',
            r'¸\s*S|S\s*¸': 'Ş', r'¸\s*s|s\s*¸': 'ş',
            r'¨\s*[uU]': 'ü',    r'¨\s*[oO]': 'ö',
        }
        for pattern, repl in mapping.items():
            text = re.sub(pattern, repl, text, flags=re.I)
        text = re.sub(r'(?<=[A-ZÇĞİÖŞÜ])\s(?=[A-ZÇĞİÖŞÜ])', '', text)
        return text

    def normalize_text(self, text: str) -> str:
        for i in ["\u2022", "-", "–", "*"]:
            text = re.sub(rf'\n?\s*{re.escape(i)}\s+', '\n', text)
        text = re.sub(r'\n{2,}', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def split_sentence(self, text: str) -> list:
        arr = []
        for line in text.split("\n"):
            parts = re.split(r'(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ])', line.strip())
            arr.extend(p.strip() for p in parts)
        return arr