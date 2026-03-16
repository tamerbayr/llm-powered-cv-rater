import os
import logging
import warnings
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning)

from pathlib import Path
import hashlib
import cv_extract
import cv_matcher
import api_client
import storage
from Processor import TextProcess

cv_dir  = Path("./docs/cvs")
job_dir = Path("./docs/jobs")

def get_file_hash(filepath: Path) -> str:
    """dosyadan hash üretir"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def load_cvs() -> list[dict]:
    """cv'leri işleyip db'ye kaydet"""
    db_cvs = {c["filename"]: c.get("file_hash") for c in storage.get_all_cvs()}
    files_raw = set()
    
    yeniler = []
    kaldirilanlar = []

    for file in sorted(cv_dir.iterdir()):
        if file.suffix.lower() not in {".pdf", ".docx", ".txt", ".json"}:
            continue
            
        files_raw.add(file.name)
        curr_hash = get_file_hash(file)
        db_hash = db_cvs.get(file.name)

        # yeni ise
        if file.name not in db_cvs or curr_hash != db_hash:
            parsed = cv_extract.pipeline(file)
            if parsed:
                storage.upsert_cv(file.name, parsed, curr_hash)
                yeniler.append(file.name)
            else:
                print(f"HATA: {file.name} işlenemedi")

    # silinenler için güncelle
    for db_filename in db_cvs.keys():
        if db_filename not in files_raw:
            storage.delete_cv(db_filename)
            kaldirilanlar.append(db_filename)

    if yeniler:
        print("Yeniler:")
        for f in yeniler:
            print(f"  - {f}")
            
    if kaldirilanlar:
        print("Kaldırılanlar:")
        for f in kaldirilanlar:
            print(f"  - {f}")

    return storage.get_all_cvs()

def list_job_files() -> list[dict]:
    if not job_dir.is_dir():
        return []

    entries = []
    for file in sorted(job_dir.iterdir()):
        if file.suffix.lower() not in {".pdf", ".docx", ".txt", ".json"}:
            continue
        db_record = storage.get_job_by_filename(file.name)
        if db_record:
            entries.append({"filename": file.name, "title": db_record["title"],
                            "id": db_record["id"], "in_db": True})
        else:
            entries.append({"filename": file.name, "title": None,
                            "id": None, "in_db": False})
    return entries

def process_job(filename) -> dict | None:
    file = job_dir / filename
    tp = TextProcess()
    raw_text = tp.read_file(file)

    exist = storage.get_job_by_filename(filename)
    
    if exist:
        if hasattr(storage, 'is_job_changed') and not storage.is_job_changed(filename, raw_text):
            return exist
        else:
            storage.delete_job(filename)

    print(f"\n[JOB] {filename} — llm ile işleniyor...")
    builder  = api_client.PromptBuilder()
    API_KEY  = api_client.get_env()
    config   = api_client.detect_provider(API_KEY)
    messages = builder.build(raw_text)
    raw_resp = api_client.post_chat(messages, config, API_KEY)
    requirement = api_client.parse_llm_response(raw_resp)

    if not requirement:
        print(f"HATA: {filename} — llm cevabı işlenemedi")
        return None

    if isinstance(requirement, dict):
        title    = requirement.get("job_title", Path(filename).stem)
        job_reqs = requirement.get("requirements", [])
    else:
        title    = Path(filename).stem
        job_reqs = requirement

    storage.upsert_job(filename, title, raw_text, job_reqs)
    return storage.get_job_by_filename(filename)

def select_job(entries: list[dict]):
    if not entries:
        print("Hiç ilan bulunamadı.")
        return None

    print("\n-- İLANLAR --")
    for i, e in enumerate(entries, 1):
        label = e["title"] if e["in_db"] and e["title"] else e["filename"]
        tag   = "" if e["in_db"] else "  (yeni)"
        print(f"  [{i}] {label}({e['filename']}){tag}")

    print("  [0] hepsini çalıştır")
    print("  [q] çıkış")

    while True:
        choice = input("\nİlan seçin: ").strip().lower()
        if choice == "q":
            return None
        if choice == "0":
            return "all"
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(entries):
                return entries[idx]
        except ValueError:
            pass
        print("geçersiz seçim...")

def score_job(job: dict, cvs: list[dict], matcher):
    job_reqs = job.get("requirements")
    job_id   = job["id"]

    if not job_reqs:
        print("HATA: gereksinim bulunamadı.")
        return

    for cv in cvs:
        print(f"-- {cv['filename']} --")
        result = matcher.score_cv(cv["parsed"], job_reqs)
        storage.upsert_score(job_id, cv["id"], result)
        print("\n")

def print_ranking(job: dict):
    scores = storage.get_scores_for_job(job["id"])

    print(f"\n-SONUÇLAR: {job['title'] or job['filename']} ===")

    if not scores:
        print("HATA: cv skorlanmadı.")
        return

    scores = sorted(scores, key=lambda x: x.get("overall_score", 0), reverse=True)

    first = scores[0].get("details", [])
    total_reqs = len(first)

    for s in scores:
        details = s.get("details", [])
        matched_count = sum(1 for d in details if d.get("is_matched"))

        print(
            f"{s['cv_filename']} - %{s['overall_score']:.2f} "
            f"({matched_count}/{total_reqs})"
        )

def print_requirements(job: dict):
    reqs = job.get("requirements", [])
    if not reqs:
        print("Gereksinim bulunamadı.")
        return
    print(f"\n=== {job['title']} — {len(reqs)} gereksinim ===\n")
    for i, r in enumerate(reqs, 1):
        name     = r.get("skill_tr") or r.get("skill_en", "?")
        rtype    = r.get("type", "?")
        priority = r.get("priority", "?")
        weight   = r.get("weight", 0)
        years    = r.get("min_years", 0)
        aliases  = ", ".join(r.get("aliases") or []) or "—"
        year_str = f"  min {years} yıl" if years else ""
        print(f"  [{i:>2}] adı: {name:<30} türü: {rtype:<15} önemi:{priority:<20} Ağırlığı{weight}{year_str}")
        print(f"  Diğer adları: {aliases}")
    print()

def main():
    storage.init_db()

    print("CV'ler yükleniyor")
    cvs = load_cvs()
    print(f"{len(cvs)} CV yüklendi")

    matcher = cv_matcher.EmbeddingCVMatcher()

    while True:
        entries = list_job_files()
        if not entries:
            print("\nİlan dosyası bulunamadı.")
            break

        selection = select_job(entries)

        if selection is None:
            print("Çıkılıyor")
            break

        if selection == "all":
            for entry in entries:
                job = process_job(entry["filename"])
                if job:
                    print_requirements(job)
                    score_job(job, cvs, matcher)
                    print_ranking(job)
        else:
            job = process_job(selection["filename"])
            if job:
                print_requirements(job)
                score_job(job, cvs, matcher)
                print_ranking(job)

        if input("\nbaşka bir ilan seçmek ister misiniz? (y/n): ").strip().lower() != "y":
            break

if __name__ == "__main__":
    main()