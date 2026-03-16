# CV Matcher

İş ilanlarını parse ederek gereksinimler çıkartan, ardından bu gereksinimlere göre CV'leri embedding tabanlı olarak puanlayıp sıralayan bir Python uygulaması.

Desteklenen dosya formatları: `.pdf`, `.docx`, `.txt`

---

## Kurulum

pip install -r requirements.txt

Kodunu CMD ile çalıştırın.

Python 3.10.11 ile geliştirilmiştir.
---

## Kullanım

### Konsol Arayüzü

```bash
python main.py
```

kodunu çalıştırın veya start.bat dosyasını açın.

İlk çalıştırmada API anahtarı istenir ve `secrets.txt` dosyasına kaydedilir. Modeller ve endpoint otomatik olarak seçilir.

Program başladığında `docs/cvs/` klasöründeki CV'leri ve `docs/jobs/` klasöründeki ilanları listeler.

Konsoldaki talimatları takip ederek ilan seçebilirsiniz.
Bir ilan seçildiğinde eğer ilan yeni veya değiştirilmişse LLM ile parse edilir. CV'ler ile eşleştirme yapılarak eşleşmeler, skorlar ve skor listesi gösterilir.


### Desteklenen LLM Sağlayıcılar

Gemini, Claude, ChatGPT ve OpenRouter desteklenir. Servis sağlayıcıyı sistem otomatik olarak anlar.
Model değiştirmek için api_client.py dosyasında detect_provider fonksiyonunu değiştirebilirsiniz.

Claude:
Endpoint: https://api.anthropic.com/v1/messages
Model: claude-3-5-haiku-20241022

ChatGPT
Endpoint: https://api.openai.com/v1/chat/completions
Model: gpt-4o-mini

Gemini
Endpoint: https://generativelanguage.googleapis.com/v1beta/openai/
Model: gemini-1.5-flash 

OpenRouter
Endpoint: https://openrouter.ai/api/v1/chat/completions
Model: "arcee-ai/trinity-large-preview:free"
(ücretsiz model)
---


## Notlar

- Program 100% doğrulukta çalışmayabilir. Gerçek hayat kullanımında karar verici program olarak kullanılmamalı, sonuçları kontrol edilmelidir.
- docs klasöründen cv veya ilan silinirse veritabanından da silinir.
- CV'ler dosya hash'i ile takip edilir. İçerik veya dosya adı değiştiğinde tekrar LLM'e gönderilir.
- Görsel taranarak oluşturulan PDF'leri DocTR ile tarar. Bu tür dosyalarda DocTR kaynaklı hatalar olabilir.
- DataBase'i temizlemek için Data klasöründeki .db dosyasını silebilirsiniz.

## Troubleshoot
-Module hatası alırsanız requirements.txt içeriğini düzgün kurduğunuzdan emin olun. Module çatışması olabileceğinden virtual enviroment kullanılması önerilir.
