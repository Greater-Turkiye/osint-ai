# Greater-Turkiye/osint-ai

[Türkçe](#türkçe) · [English](#english)

![data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-blue) ![code: MIT](https://img.shields.io/badge/code-MIT-green) ![status: design](https://img.shields.io/badge/status-design-lightgrey)

Uydu ve harita görüntülerinden OSINT adayları çıkarmayı hedefleyen çalışmanın **tasarım deposu**.
The **design repository** for turning satellite and map imagery into OSINT candidates.

> **Durum: Tasarım.** Bu depoda eğitilmiş model, model çıkarımı (inference) ve indirilmiş görüntü **yoktur**.
> **Status: design.** There is **no** trained model, no inference and no downloaded imagery in this repository.

---

## Türkçe

### Bu depo nedir?

Sahibinin isteği açıktı: "OSINT taramasını tam otomatikleştiren, milyonlarca harita/uydu görüntüsünü tarayan bir yapay zekâ." Bu depo o hedefe giden yolu, **sıfır bütçeyle gerçekten yapılabilecek** biçimde yazar. Bugün elimizde olan şey bir plan, bir kırmızı çizgi kapısı ve çalışan küçük bir iskelettir.

| Bölüm | Durum | Açıklama |
|---|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | **Taslak** | Önerilen hat: kaynak → parçalama (tiling) → gömme (embedding) → değişim tespiti → aday sıralama → **mevcut** insan inceleme kuyruğu. Her aşamanın ücretsiz katmandaki maliyeti sayıyla yazılıdır |
| [`MODELS.md`](MODELS.md) | **Taslak** | Temel model sorusunun kanıtlı cevabı: lisans, boyut, VRAM ve ücretsiz olarak nerede çalıştığı. Birinci tercih ve yedek; LoRA ile gerçekçi olarak ne kazanılır; neyin **mümkün olmadığı** |
| [`DATA.md`](DATA.md) | **Taslak** | Görüntü ve üstveri kaynakları; her biri lisansı, erişimi, çözünürlüğü, tekrar geçiş süresi ve kotasıyla. "Milyonlarca görüntü" sorusunun gerçekçi cevabı |
| [`EVALUATION.md`](EVALUATION.md) | **Taslak** | Nasıl bileceğiz: küçük etiketli ölçüt kümesi, kesinlik/duyarlılık hedefleri ve **mevcut anahtar kelime süzgecini geçemeyen model yayına girmez** kuralı |
| [`src/gt_osint_ai`](src/gt_osint_ai) | **Çalışıyor** | Küçük Python iskeleti: kırmızı çizgi kapısı, ücretsiz STAC kataloğu araması, iş hacmi hesabı. Model yok, indirme yok, kimlik bilgisi yok |
| `config/areas.yaml` | **Çalışıyor** | İzleme alanları. Hiçbiri etkin değil; Türkiye çitine değen bir kutu dosyaya **hiç yazılamaz**, yükleme hata verir |

### Bu depo ne **değildir**

- **Hedefleme aracı değildir.** Çıktısı "şuraya bak" değil, "bir insan şuna baksın"dır.
- **Otomatik yayıncı değildir.** Model çıktısı doğrudan hiçbir yere yayımlanmaz; `platform`'daki **mevcut** inceleme kuyruğuna (`gt-ops.reviews`, Telegram inceleme botu, GitHub kuyruk konusu) bir aday olarak girer ([ADR 0007](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0007-human-in-the-loop-publishing.md)).
- **Türkiye'yi izlemez.** Görüntü analizi Türkiye toprağına, iç sularına ve karasularına + 15 deniz mili emniyet payına **hiç girmez**. Bu bir süzgeç değil, bir kapıdır: alan reddedilir, katalog bile sorgulanmaz.
- **Ticari görüntü kullanmaz.** Maxar, Planet ve benzerleri lisans gereği kapsam dışıdır.
- **Sıfırdan temel model eğitmez.** Bunun için gereken GPU bütçesi yoktur ve olduğunu söylemek yalan olur ([MODELS.md](MODELS.md)).

### Değişmez kurallar

- **Hiçbir şey insan onayı olmadan yayımlanmaz.** Model önerir, insan karar verir ([ADR 0007](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0007-human-in-the-loop-publishing.md)).
- **Türk kuvvetlerinin konum ve hareketleri toplanmaz, analiz edilmez, yayımlanmaz** ([kırmızı çizgiler](https://github.com/Greater-Turkiye/handbook/blob/main/tr/02-red-lines.md), [ADR 0013](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0013-map-layers-turkiye-perspective.md), [ADR 0015](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0015-announced-operation-areas.md)). Görüntü tarafındaki karşılığı [`redlines.py`](src/gt_osint_ai/redlines.py) coğrafi çit kapısıdır; referans uygulama `platform/collectors/src/gt_collectors/geo.py`'dir ve buraya değiştirilmeden kopyalanmıştır.
- **Her kaynağın lisansı, kullanılmadan önce kayda geçer.** Görüntü yeniden dağıtılmaz; yalnızca **türetilmiş öznitelikler** ve karmalar (hash) saklanır ([ADR 0009](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0009-licensing.md), [DATA.md](DATA.md)).
- **Sıfır bütçe.** Hiçbir hesapta ödeme yöntemi yoktur; ücretsiz sınırlar aşılamaz tavandır ([ADR 0008](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0008-zero-budget-infrastructure.md)). Para veya kiralık GPU gerektiren her fikir, önerildiği cümlede bunu söyler.
- **Gizli anahtar yoktur.** Bu depodaki hiçbir kod kimlik bilgisi istemez; STAC kataloğu hesapsız çalışır.

### Diğer depolarla ilişkisi

```
osint-ai  --(aday: görüntü + gerekçe + güven)-->  platform (gt-ops.reviews)
                                                     |
                                              insan kararı (Telegram botu / kuyruk konusu)
                                                     |
                                                     v
                                              datasets (kayıt, PR incelemesi)
```

- **`platform`** sinyalleri toplar ve inceleme kuyruğunu işletir. Bu depo **yeni bir kuyruk açmaz**; adaylarını o kuyruğa yazar. Şema `platform/db/migrations/ops` içindedir.
- **`datasets`** doğrulanmış kayıtları tutar. Bir aday ancak iki insan kapısından geçtikten sonra kayda dönüşür.
- **`handbook`** kuralların kaynağıdır. Bu deponun kendisi ve buradaki yapay zekâ kuralları [ADR 0017](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0017-osint-ai-repository.md) ile önerilmiştir.

### Kurulum ve çalıştırma

```bash
python -m pip install -e ".[dev]"
python -m pytest -m "not network"     # birim testler; ağ istemez
ruff check . && ruff format --check .
```

Bugün gerçekten çalışan tek uçtan uca iş: bir kutu ve tarih aralığı verilir, kırmızı çizgi kapısından geçirilir, ücretsiz STAC kataloğundan hangi açık uydu sahnelerinin var olduğu sorulur ve **yapılacak işin hacmi** yazdırılır.

```bash
# Kıbrıs'ın güneyinde açık deniz: izin verilir
gt-osint-ai scenes --bbox 32.0,33.2,33.0,33.9 --from 2025-06-01 --to 2025-06-30

# Ankara: reddedilir, katalog sorgulanmaz, çıkış kodu 2
gt-osint-ai scenes --bbox 32.6,39.7,33.1,40.1 --from 2025-06-01 --to 2025-06-30

# Alanları doğrula ve listele
gt-osint-ai areas --config config/areas.yaml
```

Çıkış kodları: `0` başarı, `1` hatalı argüman veya erişilemeyen katalog, `2` **kırmızı çizgi reddi**. `2` bilerek ayrıdır: bir reddi "sonuç bulunamadı" ile karıştırmak mümkün olmasın.

### Lisans

Kod [MIT](LICENSE); belgeler ve veri [CC BY 4.0](LICENSE-DATA) ([ADR 0009](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0009-licensing.md)). Üçüncü taraf görüntü kaynaklarının lisansları [DATA.md](DATA.md) içinde tek tek künyelenir.

---

## English

### What this repository is

The owner's ask was plain: "an AI that fully automates OSINT scanning and reads millions of map and satellite images." This repository writes down the route to that, limited to **what is actually achievable on zero budget**. What exists today is a plan, a red-line gate, and a small skeleton that runs.

| Part | Status | What it is |
|---|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | **Draft** | The pipeline we recommend: source → tiling → embedding → change detection → candidate ranking → the **existing** human review queue. Each stage costed in free-tier terms with real numbers |
| [`MODELS.md`](MODELS.md) | **Draft** | The base-model question answered with evidence: licence, size, VRAM and where each one runs for free. A first choice and a fallback, what LoRA realistically adds, and what is **not** feasible |
| [`DATA.md`](DATA.md) | **Draft** | Imagery and metadata sources, each with licence, access, resolution, revisit time and quota. A realistic answer to "millions of images" |
| [`EVALUATION.md`](EVALUATION.md) | **Draft** | How we will know it works: a small labelled benchmark, precision/recall targets, and the rule that **a model that cannot beat the existing keyword filter does not ship** |
| [`src/gt_osint_ai`](src/gt_osint_ai) | **Working** | A small Python skeleton: the red-line gate, a free STAC catalogue search, and the work arithmetic. No model, no download, no credential |
| `config/areas.yaml` | **Working** | Areas of interest. None is enabled, and a box touching the Türkiye geofence **cannot be written into the file at all** — loading fails |

### What it is **not**

- **Not a targeting tool.** Its output is never "strike here", it is "a person should look at this".
- **Not an auto-publisher.** Model output is published nowhere. It enters the **existing** review queue in `platform` (`gt-ops.reviews`, the Telegram review bot, the GitHub queue issue) as a candidate ([ADR 0007](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0007-human-in-the-loop-publishing.md)).
- **Not a watcher of Türkiye.** Imagery analysis never enters Turkish land, internal waters or territorial sea plus a 15 nm standoff. This is a gate, not a filter: the area is refused and the catalogue is not even queried.
- **Not a user of commercial imagery.** Maxar, Planet and similar are out of scope on licence grounds.
- **Not training a foundation model from scratch.** We do not have the GPU budget for that, and saying otherwise would be a lie ([MODELS.md](MODELS.md)).

### Rules that do not bend

- **Nothing is published without human approval.** The model proposes, a person decides ([ADR 0007](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0007-human-in-the-loop-publishing.md)).
- **Positions and movements of Turkish forces are never collected, analysed or published** ([red lines](https://github.com/Greater-Turkiye/handbook/blob/main/tr/02-red-lines.md), [ADR 0013](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0013-map-layers-turkiye-perspective.md), [ADR 0015](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0015-announced-operation-areas.md)). On the imagery side that is the geofence gate in [`redlines.py`](src/gt_osint_ai/redlines.py); the reference implementation is `platform/collectors/src/gt_collectors/geo.py`, vendored here unchanged.
- **Every source's licence is recorded before it is used.** Imagery is never redistributed; we keep **derived features** and hashes only ([ADR 0009](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0009-licensing.md), [DATA.md](DATA.md)).
- **Zero budget.** No account has a payment method; free-tier limits are hard caps ([ADR 0008](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0008-zero-budget-infrastructure.md)). Anything needing money or a GPU we do not have says so in the sentence that proposes it.
- **No secrets.** No code here asks for a credential; the STAC catalogue works without an account.

### How it connects to the other repositories

```
osint-ai  --(candidate: tile + reason + confidence)-->  platform (gt-ops.reviews)
                                                            |
                                                 human decision (Telegram bot / queue issue)
                                                            |
                                                            v
                                                   datasets (record, PR review)
```

- **`platform`** collects signals and runs the review queue. This repository **does not open a second queue**; it writes candidates into that one. The schema lives in `platform/db/migrations/ops`.
- **`datasets`** holds verified records. A candidate becomes a record only after both human gates.
- **`handbook`** is the authority for the rules. This repository and its AI rules are proposed in [ADR 0017](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0017-osint-ai-repository.md).

### Install and run

```bash
python -m pip install -e ".[dev]"
python -m pytest -m "not network"     # unit tests; no network needed
ruff check . && ruff format --check .
```

The one thing that genuinely works end to end today: give it a bounding box and a date range,
it runs the red-line gate, asks the free STAC catalogue which open scenes exist, and prints
**how much work a pass would be**.

```bash
# Open sea south of Cyprus: allowed
gt-osint-ai scenes --bbox 32.0,33.2,33.0,33.9 --from 2025-06-01 --to 2025-06-30

# Ankara: refused, the catalogue is never queried, exit code 2
gt-osint-ai scenes --bbox 32.6,39.7,33.1,40.1 --from 2025-06-01 --to 2025-06-30

# Validate and list the configured areas
gt-osint-ai areas --config config/areas.yaml
```

Exit codes: `0` success, `1` a bad argument or an unreachable catalogue, `2` a **red-line
refusal**. `2` is deliberately distinct so a refusal can never be read as "no results".

### Licence

Code is [MIT](LICENSE); documentation and data are [CC BY 4.0](LICENSE-DATA)
([ADR 0009](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0009-licensing.md)).
Third-party imagery licences are recorded one by one in [DATA.md](DATA.md).
