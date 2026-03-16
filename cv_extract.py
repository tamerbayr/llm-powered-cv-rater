#cv'leri işlemek için formatlar

import re
import datetime
from pathlib import Path
from rapidfuzz import fuzz
from Processor import TextProcess
import json
 
_processor = TextProcess()

fuzzy_threshold = 75

_skill_stopword = {
    "from", "big", "using", "doing", "loading", "they", "filling",
    "missing", "college", "helps", "view", "city", "ad", "draw",
    "edit", "type", "sales", "clients", "research", "reporting",
    "servers", "scripts", "tables", "networks", "neural", "database",
    "middleware", "programming", "validation", "to", "and", "or",
    "the", "a", "an", "of", "in", "for", "with", "on", "at",
    "gt", "int", "ofl", "tol", "bigl", "andl", "onl",
}

map_section = {
    "experience": [
        "deneyim", "tecrübe", "iş geçmişi", "experience", "work history",
        "work experience", "professional experience", "iş deneyimi", "kariyer",
        "employment history", "employment", "work",
    ],
    "education": [
        "eğitim", "öğrenim", "education", "academic background",
        "eğitim bilgileri", "akademik geçmiş", "education and training",
        "education & training", "eğitim ve öğrenim", "academic",
    ],
    "summary": [
        "hakkımda", "özet", "profil", "about me", "summary", "objective",
        "kişisel profil", "career objective", "professional summary",
        "profile", "about", "professional profile", "personal statement",
        "career summary",
    ],
    "projects": [
        "projeler", "projects", "kişisel projeler", "personal projects",
        "side projects", "çalışmalar",
    ],
    "skills": [
        "yetenekler", "beceriler", "skills", "yetkinlik", "yetenek",
        "beceri", "yetkinlikler", "technical skills", "core skills",
        "key skills", "teknik beceriler", "competencies", "expertise",
        "areas of expertise", "core competencies", "technical expertise",
    ],
    "certifications": [
        "sertifikalar", "certifications", "belgeler", "sertifika",
        "certificates", "licenses", "accreditations", "credentials",
        "professional development",
    ],
    "languages": [
        "diller", "languages", "yabancı dil", "yabancı diller",
        "language skills", "dil becerileri",
    ],
    "affiliations": [
        "affiliations", "memberships", "professional affiliations",
        "associations", "professional memberships",
    ],
}

map_derece = {
    "doktora":       ["doktora", "phd", "ph.d", "doctor"],
    "yüksek lisans": ["yüksek lisans", "master", "msc", "mba", "m.s", "m.a"],
    "lisans":        ["lisans", "bachelor", "bsc", "b.s", "b.a"],
    "önlisans":      ["ön lisans", "associate"],
    "lise":          ["lise", "lisesi", "highschool", "high school"],
}

aylar = (
        "january|february|march|april|may|june|july|august|"
        "september|october|november|december|"
        "ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|"
        "eylül|ekim|kasım|aralık"
    )
regex_year_range = re.compile(
        r'(?:\d{2}/)?(\d{4})\s*(?:[-–—]|to)\s*'
        r'(?:\d{2}/)?(\d{4}|devam|present|current|günümüz)',
        re.IGNORECASE
    )
regex_year_single = re.compile(rf'(?:(?:{aylar})\s+)?(\d{{4}})', re.IGNORECASE)

regex_degree = [
        "bachelor", "master", "phd", "ph.d", "doktora", "mba",
        "yüksek lisans", "ön lisans", "lisans", "associate degree",
        "doctor of", "m.s", "m.a", "b.s", "b.a", "msc", "bsc",
    ]
regex_uni = [
        "university", "üniversite", "institute", "enstitü",
        "fakülte", "college", "school of", "academy",
    ]

# -eğitim

def detect_degree_type(text):
    text = _processor.turkish_lower(text)
    for degree, keywords in map_derece.items():
        if any(a in text for a in keywords):
            return degree
    return "lisans"


def detect_degree_status(end_year_str):
    """bitiş yılına göre meznun olup olmadığı"""
    current_year = datetime.datetime.now().year
    if not end_year_str:
        return "belirtilmemiş"
    
    end_str = _processor.turkish_lower(str(end_year_str))
    if any(x in end_str for x in ["devam", "present", "current", "günümüz"]):
        return "öğrenci"
    try:
        return "öğrenci" if int(end_str) > current_year else "mezun"
    except ValueError:
        return "belirtilmemiş"
    
def parse_education_section(education_text: str) -> list:
    results = []
    if not education_text:
        return results

    def _is_degree(line: str) -> bool:
        tl = _processor.turkish_lower(line).lstrip("•-– ")
        if any(tl.startswith(kw) for kw in regex_degree):
            return True
        words = tl.split()
        if not words:
            return False
        first_one = words[0]
        first_two = " ".join(words[:2]) if len(words) >= 2 else first_one
        for kw in regex_degree:
            if len(kw) < 4:
                continue
            if (fuzz.ratio(first_one, kw) >= 80 or
                    fuzz.ratio(first_two, kw[:len(first_two)]) >= 80):
                return True
        return False

    def _is_uni(line: str) -> bool:
        if len(line) > 100:
            return False
        line = _processor.turkish_lower(line)
        return any(kw in line for kw in regex_uni)

    def _extract_date(line: str):
        m = regex_year_range.search(line)
        if m:
            clean = regex_year_range.sub("", line).strip().strip("-–—:, ")
            return m.group(1), m.group(2), clean
        m = regex_year_single.search(line)
        if m:
            year = m.group(1)
            before = line[:m.start()].strip().strip("-–—:, ")
            after  = line[m.end():].strip().strip("-–—:, ")
            clean  = before or after or line
            clean = re.sub(rf'\b(?:{aylar})\s*:?\s*$', '', clean, flags=re.I).strip().strip("-–—:, ")
            return None, year, clean
        return None, None, line.strip()

    lines = [l.strip() for l in education_text.split("\n") if l.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_degree(line):
            start_year, end_year, degree_clean = _extract_date(line)
            degree_name = degree_clean.strip(" -–—,()") or line

            uni_name = None
            for n in range(1, 4):
                if i + n < len(lines):
                    next_line = lines[i + n]
                    if _is_uni(next_line):
                        uni_start, uni_end, uni_temiz = _extract_date(next_line)
                        uni_name = uni_temiz.strip(" -–—,()")
                        if uni_end and not end_year: end_year = uni_end
                        if uni_start and not start_year: start_year = uni_start
                        i += n
                        break
                    elif _is_degree(next_line):
                        break

            results.append({
                "degree":        degree_name,
                "university":    uni_name,
                "degree_type":   detect_degree_type(degree_name),
                "degree_status": detect_degree_status(end_year),
                "start_year":    start_year,
                "end_year":      end_year,
            })
        elif _is_uni(line) and not results:
            start_year, end_year, uni_clean = _extract_date(line)
            results.append({
                "degree":        None,
                "university":    uni_clean.strip(" -–—,"),
                "degree_type":   detect_degree_type(uni_clean),
                "degree_status": detect_degree_status(end_year),
                "start_year":    start_year,
                "end_year":      end_year,
            })
        i += 1

    return results

# -başlık

def _clean_ocr_noise(text):
    """ocr hatasını azaltmak için kelime sonundaki hataları düzeltmeye çalışır"""
    text = re.sub(r'([a-z])\1+$', r'\1', text)   # skillss -> skills
    text = re.sub(r'([a-z]{5,})[a-z]$', r'\1', text)   # skillso -> skills
    return text.strip()


def _find_header(line) -> str | None:
    """
    satırın bölüm başlığı olup olmadığını fuzzy matching ile kontrol eder
    eşleşirse section key döner yoksa None
    """
    line = re.sub(r'^[•*\-=_\s]+', '', _processor.turkish_lower(line)).strip().rstrip(":").strip()

    if len(line) < 2 or len(line) > 50:
        return None

    blacklist = {"öğrenme", "learning", "machine learning", "makine öğrenmesi", "deep learning", "derin öğrenme"} # öğrenmeyi görünce eğitim başlığına geçmesin diye
    if line in blacklist:
        return None

    adaylar = [line]
    temiz = _clean_ocr_noise(line)
    if temiz != line: # hem bozuk hem de "düzeltilmiş" versiyonu deniyor
        adaylar.append(temiz)

    best_sec = None
    best_skor = 0
    for aday in adaylar:
        for key, words in map_section.items():
            for a in words:
                if aday == a:
                    return key
                score = fuzz.ratio(aday, a)
                if score > best_skor:
                    best_skor, best_sec = score, key

    return best_sec if best_skor >= fuzzy_threshold else None

# -bölümlere ayırma

regex_date = re.compile(
    r'(?:\d{2}/)?(\d{4})\s*(?:[-–—]|to)\s*(?:\d{2}/)?(\d{4}|günümüz|present|current)',
    re.I
)
regex_start  = re.compile(r'^\d{4}\s*[-–—]\s*$', re.I)
regex_single = re.compile(r'^\(?\d{4}\)?$', re.I)


def _normalize_date(text):
    m = regex_date.search(text)
    if not m:
        return text
    
    start_year, end_year = m.group(1), m.group(2)
    temiz = regex_date.sub('', text).strip().strip("(),;-")
    date_str = f"({start_year}-{end_year})"
    return f"{temiz} {date_str}".strip() if temiz else date_str


def _split_skill_line(line) -> list:
    parts = re.compile(r'[,;|•]').split(line)
    skills = []
    
    for p in parts:
        p = p.strip().strip("-–—").strip()
        if not p or p.isdigit():
            continue
        if _processor.turkish_lower(p) in _skill_stopword:
            continue
        skills.append(p)
    return skills


def text_to_sections(text) -> dict:
    """
    başlıkları tespit edip bölümlere ayırır
    başlık bulma yöntemleri: tamamen küçük harf olmayan, nokta ile bitmeyen, çok uzun veya kısa olmayan
    """
    sections = {k: [] for k in map_section}
    sections["general"] = []

    current = "general"
    pending_date = None
    raw_lines = []

    for line in text.splitlines():
        line = _processor.fix_turkish(line.strip())
        if not line:
            continue
            
        spaced_line = re.sub(r'([.!?])([A-Z][a-z]{3,})', r'\1\n\2', line)
        for part in spaced_line.split('\n'):
            part = part.strip()
            if part:
                raw_lines.append(part)

    merged_lines = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        if _find_header(line):
            merged_lines.append(line)
            i += 1
            continue
        if (i + 1 < len(raw_lines)
                and len(line) <= 30
                and len(raw_lines[i + 1]) <= 30
                and _find_header(line + " " + raw_lines[i + 1])):
            merged_lines.append(line + " " + raw_lines[i + 1])
            i += 2
            continue
        merged_lines.append(line)
        i += 1

    def _append_to_section(sections_dict, current_sec, content_val):
        if not content_val:
            return
        val = _normalize_date(content_val)
        if current_sec == "skills":
            for skill in _split_skill_line(val):
                sections_dict["skills"].append(skill)
        elif current_sec in ("summary", "experience") and sections_dict[current_sec]:
            last = sections_dict[current_sec][-1]
            if not last.endswith(")") and val and val[0].islower():
                sections_dict[current_sec][-1] += " " + val
            else:
                sections_dict[current_sec].append(val)
        else:
            sections_dict[current_sec].append(val)

    for line in merged_lines:
        if regex_start.match(line):
            pending_date = line
            continue

        if pending_date and regex_single.match(line):
            if sections[current]:
                sections[current][-1] += f" ({pending_date}{line})"
            pending_date = None
            continue

        if regex_single.match(line) and sections[current]:
            sections[current][-1] += f" ({line})"
            continue

        header = _find_header(line)
        if header:
            current = header
            continue

        if ":" in line:
            prefix, suffix = line.split(":", 1)
            inline_header = _find_header(prefix)
            if inline_header:
                current = inline_header
                _append_to_section(sections, current, suffix.strip())
                continue

        _trailing_found = False
        if not line.strip().endswith('.') and len(line) < 120:
            words = line.split()
            for suffix_len in (1, 2):
                if len(words) <= suffix_len:
                    continue
                
                suffix = " ".join(words[-suffix_len:])
                
                if suffix.islower() and len(words) > 3:
                    continue

                trailer_header = _find_header(suffix)
                if trailer_header:
                    content_part = " ".join(words[:-suffix_len]).strip()
                    _append_to_section(sections, current, content_part)
                    current = trailer_header
                    _trailing_found = True
                    break

        if _trailing_found:
            continue

        _append_to_section(sections, current, line)

    seen, unique = set(), []
    for s in sections["skills"]:
        k = _processor.turkish_lower(s)
        if k not in seen:
            seen.add(k)
            unique.append(s)
    sections["skills"] = unique

    return {k: "\n".join(v) for k, v in sections.items()}

# -skill

regex_skill_range = re.compile(
    r'(?:\d{2}/)?(\d{4})\s*(?:[-–—]|to)\s*(?:\d{2}/)?(\d{4}|günümüz|present|current)', 
    re.IGNORECASE
)

regex_skill_dur = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(?:yıl|sene|year)', 
    re.IGNORECASE
)

def _parse_end_year(end_str, current_year) -> int:
    lower_e = _processor.turkish_lower(end_str)
    if any(k in lower_e for k in {'günümüz', 'present', 'current'}):
        return current_year
    return int(end_str)

def calculate_duration(text, keyword, current_year) -> list:
    intervals = []
    search_kw = _processor.turkish_lower(keyword)
    
    for line in text.split("\n"):
        if search_kw not in _processor.turkish_lower(line):
            continue
            
        for s, e_str in regex_skill_range.findall(line):
            s_yr = int(s)
            e_yr = _parse_end_year(e_str, current_year)
            if e_yr > s_yr:
                intervals.append((s_yr, e_yr))
    return intervals

def _merge_sum(intervals: list) -> int:
    if not intervals:
        return 0
    intervals.sort()
    merged = [list(intervals[0])]
    for x, y in intervals[1:]:
        if x <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], y)
        else:
            merged.append([x, y])
    return sum(y - x for x, y in merged)

def extract_skill_years(sec):
    current_year = datetime.datetime.now().year
    result = {}
    skills = sec.get("skills", "")
    experience = sec.get("experience", "")
    projects = sec.get("projects", "")

    for skill in skills.split("\n"):
        skill = skill.strip()
        if not skill:
            continue
            
        if _processor.turkish_lower(skill) in _skill_stopword:
            continue

        match_range = regex_skill_range.search(skill)
        match_dur= regex_skill_dur.search(skill)
        
        #temizleme (2 defa olması hata değil)
        skill_name = regex_skill_range.sub("", skill)
        skill_name = regex_skill_dur.sub("", skill_name).strip(" ()-,")

        if not skill_name:
            continue

        if match_range:
            start_year = int(match_range.group(1))
            end_year = _parse_end_year(match_range.group(2), current_year)
            result[skill_name] = max(0.5, float(end_year - start_year))
            
        elif match_dur:
            result[skill_name] = float(match_dur.group(1).replace(",", "."))
            
        else:
            duration = calculate_duration(experience, skill_name, current_year) + \
                        calculate_duration(projects, skill_name, current_year)
            total = _merge_sum(duration)
            result[skill_name] = max(float(total), 0.0)

    return result

####

def pipeline(cv_path) -> dict | None:
    """
    returns:
        general, summary, experience, education, skills, certifications, languages, projects, affiliations, education_structured, skill_years
    """
    cv_path = Path(cv_path)

    if not cv_path.exists():
        print(f"{cv_path} bulunamadı")
        return None

    try:
        raw_text = _processor.read_file(cv_path)
    except ValueError as e:
        print(e)
        return None
    
    sections = text_to_sections(raw_text)

    result = {}
    for key, val in sections.items():
        val = val.lower().strip()
        val = re.sub(r'[ \t]+', ' ', val)
        val = val.replace('•', '')
        result[key] = val

    result["education_structured"] = parse_education_section(result.get("education", ""))
    result["skill_years"]          = extract_skill_years(result)

    return result

if __name__ == '__main__':
    cv = pipeline(Path(r".\docs\cvs\emrekaya(robot).txt"))
    if cv:
        print("---DEBUG---")
        for sec, content in cv.items():
            print(f"\n--- {sec.upper()} ---")
            if isinstance(content, (list, dict)):
                print(json.dumps(content, ensure_ascii=False, indent=2))
            else:
                print(content[:500] if len(content) > 500 else content)
        print("\n---DEBUG END---")