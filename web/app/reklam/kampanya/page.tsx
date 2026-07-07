"use client";

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactElement,
} from "react";
import Link from "next/link";
import {
  suggestAdPackages,
  createAdCampaign,
  getAdCampaign,
  getAdCampaignReport,
  generateSpotScript,
  listSpotVoices,
  synthesizeSpotVoice,
  requestJingle,
  listJingles,
  getCampaignProof,
  autoJingle,
  pollJingle,
  jingleFileUrl,
  mixAd,
  apiFileUrl,
  planAd,
  produceAd,
  makeMusic,
  type AdPackage,
  type AdCampaign,
  type AdCampaignOrderBreakdown,
  type AdCampaignReport,
  type SpotVoice,
  type JingleLibraryItem,
  type JingleRequest,
  type FingerprintDetection,
  type AutoJingle,
  type AdPlan,
  type AdPlanSfx,
  type ProduceAdResult,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type Daypart = "sabah" | "gunduz" | "drive" | "aksam" | "gece";
type BuyerKind = "artist" | "business";
type PackageKey = "opening" | "weekend" | "monthly" | "custom";
/** Sihirbaz giris modu: yonetmen = tek-tik tam otomatik, adim = mevcut 6 adim. */
type WizardMode = "director" | "steps";

/** Backend enum sirasi ile ayni (bkz. web/app/reklam/page.tsx). */
const DAYPARTS: Daypart[] = ["sabah", "gunduz", "drive", "aksam", "gece"];
const SECONDS_OPTIONS = [15, 20, 30] as const;
const TONE_OPTIONS = ["enerjik", "samimi", "profesyonel", "eglenceli"] as const;

const T = {
  tr: {
    logo: "MuzikSEO",
    heading: "Kampanya Sihirbazı",
    intro:
      "6 adımda kendi radyo reklam kampanyanı kur: hedefini seç, spotunu AI ile yaz, istersen seslendir ve jingle ekle, müzik + sesi birleştir, sonra tek onayla yayına al.",
    // --- Mod secimi ---
    modeChooserTitle: "Nasıl ilerlemek istersin?",
    directorModeTitle: "🎬 Reklam Yönetmeni (Tek Tık, Önerilen)",
    directorModeDesc:
      "Ürün adını ve birkaç detayı gir, gerisini AI halletsin: reklam planı, müzik, efektler, seslendirme — hepsi tek seferde üretilip birleştirilir.",
    stepModeTitle: "🔧 Adım Adım (Gelişmiş)",
    stepModeDesc:
      "Her aşamayı kendin yönet: hedef seç, spot metnini yaz, sesi ve jingle'ı ayrı ayrı seç, sonra birleştir.",
    backToModesBtn: "‹ Mod Seç",
    // --- Reklam Yonetmeni (tek-tik otomatik) ---
    directorHeading: "Reklam Yönetmeni",
    directorIntro:
      "Ürün/sanatçı adını ve detayları gir — AI önce bir reklam planı çıkarır (müzik, seslendirme metni, efektler), sen istersen düzenlersin, sonra tek tıkla tam reklamı üretirsin.",
    directorVoiceLabel: "Seslendirme Sesi (ElevenLabs)",
    directorStep1Btn: "1) Reklam Planı Oluştur",
    directorStep1Busy: "Plan hazırlanıyor...",
    directorPlanTitle: "Reklam Planı (düzenlenebilir)",
    directorTotalSecondsLabel: "Toplam süre (sn)",
    directorMusicPromptLabel: "Müzik Açıklaması",
    musicPreviewBtn: "🎧 Müziği Önce Dinle",
    musicPreviewBusy: "Müzik üretiliyor...",
    musicPreviewReadyLabel: "Müzik önizlemesi:",
    musicPreviewError: "Müzik önizlemesi üretilemedi, tekrar dene.",
    directorVoiceoverLabel: "Seslendirme Metni",
    directorVoiceDelayLabel: "Seslendirme gecikmesi (sn)",
    directorSfxTitle: "Ses Efektleri",
    directorSfxPromptLabel: "Efekt açıklaması",
    directorSfxAtLabel: "Kaçıncı saniyede",
    directorSfxDurationLabel: "Süre (sn)",
    directorSfxAddBtn: "+ Efekt Ekle",
    directorSfxRemoveBtn: "Sil",
    directorSfxEmpty: "Efekt yok.",
    directorNotesLabel: "Notlar",
    directorStep2Btn: "2) Reklamı Üret",
    directorStep2Busy: "Üretiliyor… (müzik+efekt+ses+mix)",
    directorProduceNote:
      "Üretim 1-2 dakika sürebilir — müzik, efektler ve seslendirme sırayla üretilip birleştirilir.",
    directorResultTitle: "Nihai Reklam Hazır",
    directorResultSummaryTemplate: "Müzik + {n} efekt + {sec} sn seslendirme",
    directorContinueBtn: "Kampanya Oluşturmaya Devam Et →",
    planRequiredError: "Önce bir reklam planı oluştur",
    steps: [
      "Hedef",
      "Spot Metni",
      "Seslendirme",
      "Jingle",
      "Reklamı Birleştir",
      "Özet + Onay",
    ],
    // --- Adim 1 ---
    cityLabel: "Şehir (opsiyonel — boş bırakırsan tüm şehirler)",
    cityPlaceholder: "Örn. İstanbul",
    daypartsLabel: "Kuşaklar",
    daypartLabels: {
      sabah: "Sabah",
      gunduz: "Gündüz",
      drive: "Drive-Time",
      aksam: "Akşam",
      gece: "Gece",
    } as Record<Daypart, string>,
    weeksLabel: "Hafta sayısı (1-12)",
    budgetLabel: "Bütçe (TL)",
    budgetPlaceholder: "Örn. 5000",
    budgetRequiredError: "Önce pozitif bir bütçe gir",
    suggestBtn: "Paketleri Gör",
    suggestBusy: "Paketler hazırlanıyor...",
    packageLabels: {
      opening: "Açılış Paketi",
      weekend: "Hafta Sonu Kampanyası",
      monthly: "1 Aylık Bilinirlik",
    } as Record<"opening" | "weekend" | "monthly", string>,
    packageStations: "istasyon",
    packageWeeklySpots: "haftalık tahmini spot",
    packageTotal: "toplam",
    packageEmpty: "Bu filtrelerle eşleşen ilan yok.",
    selectBtn: "Bu Paketi Seç",
    selectedBtn: "Seçildi",
    customOption: "Özel: filtrelerimle devam et",
    customOptionNote: "Girdiğin hafta sayısı ve kuşaklarla devam eder.",
    // --- Adim 2 ---
    productNameLabel: "Ürün / Sanatçı adı",
    productNamePlaceholder: "Örn. Yeni albüm 'Gece Yarısı'",
    detailsLabel: "Detaylar",
    detailsPlaceholder: "Ürünün/etkinliğin öne çıkan özellikleri, tarih, yer...",
    secondsLabel: "Süre",
    toneLabel: "Ton",
    toneLabels: {
      enerjik: "Enerjik",
      samimi: "Samimi",
      profesyonel: "Profesyonel",
      eglenceli: "Eğlenceli",
    } as Record<(typeof TONE_OPTIONS)[number], string>,
    generateBtn: "AI ile Metin Üret",
    generateBusy: "Üretiliyor...",
    productNameRequiredError: "Önce ürün/sanatçı adını gir",
    scriptEditableLabel: "Spot metni (düzenlenebilir)",
    scriptTemplateNote:
      "ANTHROPIC_API_KEY tanımlı değil — şablon metin üretildi (yine de kullanılabilir).",
    kuponNote:
      "Metindeki {KUPON} yer tutucusu — kampanya onaylandığında gerçek kupon koduyla değişir.",
    scriptRequiredError: "Devam etmek için bir spot metni gerekli",
    // --- Adim 3 ---
    voiceStepTitle: "Seslendirme (opsiyonel)",
    voiceStepNote:
      "Bu adımı atlayabilirsin — spot metnini radyo kendi sunucusuyla da okuyabilir.",
    voicesLoading: "Sesler yükleniyor...",
    voiceBtn: "Seslendir",
    voiceBusy: "Seslendiriliyor...",
    audioReadyLabel: "Hazır önizleme:",
    skipBtn: "Bu Adımı Atla",
    // --- Ses secici (VoiceLibraryPicker) ---
    voiceSearchPlaceholder: "Ses ara (isimle filtrele)...",
    voicesEmpty: "Aramanla eşleşen ses yok.",
    voiceListenLabel: "Dinle",
    voiceSelectBtn: "Seç",
    voiceSelectedBtn: "Seçili",
    // --- Adim 4 ---
    jingleStepTitle: "Jingle (opsiyonel)",
    autoJingleTitle: "AI ile Otomatik Jingle",
    autoJingleNote:
      "2. adımdaki ürün/sanatçı adı ve detaylara uygun bir jingle üretir (Suno).",
    autoJingleBtn: "🎵 Senaryoma Uygun Jingle Üret (AI)",
    autoJingleBusy: "Üretiliyor...",
    autoJingleGeneratingMsg: "Jingle üretiliyor, biraz zaman alabilir...",
    autoJingleReadyLabel: "Hazır jingle önizlemesi:",
    orDivider: "— veya —",
    jingleLibraryTitle: "Hazır Jingle Kütüphanesi",
    jingleLibraryEmpty: "Şu an hazır jingle yok.",
    jinglePreviewUnavailable: "Bu jingle için önizleme henüz mevcut değil.",
    jingleReadyTitle: "Hazırlanan özel jingle talepleri",
    selectJingleBtn: "Bu Jingle'ı Seç",
    selectedJingleBtn: "Seçildi",
    customJingleTitle: "Özel Jingle İste",
    briefLabel: "Brief",
    briefPlaceholder: "Marka/ürün, mesaj, istenen atmosfer...",
    styleLabel: "Stil (opsiyonel)",
    stylePlaceholder: "Örn. akustik, elektronik, epik...",
    requestBtn: "Jingle Talep Et",
    requestBusy: "Gönderiliyor...",
    briefRequiredError: "Brief boş olamaz",
    jingleQueuedMsg:
      "Talebin kuyruğa alındı, hazırlanınca kampanyana bağlanır.",
    // --- Adim 5 ---
    mixStepTitle: "Reklamı Birleştir",
    mixStepDesc:
      "Müzik sesin altında çalar, reklam bitince yumuşak kapanır — radyoya gönderilecek hazır spot budur.",
    mixBtn: "🎬 Reklamı Oluştur (müzik + ses)",
    mixBusy: "Birleştiriliyor...",
    mixNeedVoiceError: "Önce seslendirme üret (3. adım)",
    mixNeedJingleError: "Önce jingle seç/üret (4. adım)",
    mixReadyLabel: "Hazır reklam:",
    mixDownloadBtn: "İndir",
    // --- Adim 6 ---
    summaryTitle: "Özet",
    summaryCity: "Şehir",
    summaryCityAll: "Tüm şehirler",
    summaryDayparts: "Kuşaklar",
    summaryDaypartsAll: "Tüm kuşaklar",
    summaryWeeks: "Hafta",
    summaryBudget: "Bütçe",
    summaryProduct: "Ürün/Sanatçı",
    summaryScript: "Spot metni",
    summaryVoice: "Seslendirme",
    summaryVoiceYes: "Hazır (önizleme mevcut)",
    summaryVoiceNo: "Yok — radyo kendi sunucusuyla okuyacak",
    summaryJingle: "Jingle",
    summaryJingleYes: "Seçildi",
    summaryJingleNo: "Yok",
    summaryMix: "Birleştirilmiş Reklam",
    summaryMixYes: "Hazır (indirilebilir)",
    summaryMixNo: "Yok",
    couponNote:
      "Kampanya onaylandığında benzersiz bir kupon kodu oluşturulur ve spot metnine eklenir.",
    commissionNote: "Toplam bedele %18 MüzikSEO komisyonu dahildir.",
    buyerNameLabel: "Adın / Şirket adın",
    buyerNamePlaceholder: "Ad Soyad veya şirket adı",
    buyerEmailLabel: "E-posta",
    buyerKindLabel: "Alıcı türü",
    buyerKindLabels: { artist: "Sanatçı", business: "İşletme" } as Record<
      BuyerKind,
      string
    >,
    buyerRequiredError: "Ad ve e-posta zorunlu",
    submitBtn: "Kampanyayı Başlat",
    submitBusy: "Kampanya oluşturuluyor...",
    backBtn: "Geri",
    nextBtn: "İleri",
    genericError: "Sunucuya ulaşılamadı, tekrar dene.",
    // --- Basari + takip ---
    successHeading: "Kampanya oluşturuldu",
    campaignNoLabel: "Kampanya No",
    couponLabel: "Kupon Kodu",
    totalLabel: "Toplam",
    trackingTitle: "Kampanyanı Takip Et",
    trackEmailLabel: "Kampanyayı oluştururken kullandığın e-posta",
    checkStatusBtn: "Durumu Sorgula",
    checkBusy: "Sorgulanıyor...",
    ordersTitle: "Sipariş Kırılımı",
    orderStatusLabels: {
      pending: "Bekliyor",
      accepted: "Kabul Edildi",
      rejected: "Reddedildi",
      paid: "Ödendi",
      airing: "Yayında",
    } as Record<AdCampaignOrderBreakdown["status"], string>,
    reportTitle: "Denetim Raporu",
    plannedSpotsLabel: "Planlanan toplam spot",
    verifiedPlaysLabel: "Teyitli yayın",
    perStationTitle: "İstasyon Kırılımı",
    proofBtn: "Kanıt Loglarını Göster",
    proofHideBtn: "Gizle",
    proofLoading: "Kanıt logları yükleniyor...",
    proofEmpty: "Henüz bir tespit kaydı yok.",
    proofScoreLabel: "eşleşme skoru",
    newCampaignBtn: "Yeni Kampanya Başlat",
  },
  en: {
    logo: "MuzikSEO",
    heading: "Campaign Wizard",
    intro:
      "Set up your own radio ad campaign in 6 steps: pick a target, write your spot with AI, optionally add voice + jingle, merge the music and voice, then confirm once to go live.",
    modeChooserTitle: "How do you want to proceed?",
    directorModeTitle: "🎬 Ad Director (One-Click, Recommended)",
    directorModeDesc:
      "Enter the product name and a few details, let AI handle the rest: ad plan, music, sound effects, voice-over — all generated and merged in one go.",
    stepModeTitle: "🔧 Step by Step (Advanced)",
    stepModeDesc:
      "Manage every stage yourself: pick a target, write the spot script, choose voice and jingle separately, then merge.",
    backToModesBtn: "‹ Choose Mode",
    directorHeading: "Ad Director",
    directorIntro:
      "Enter the product/artist name and details — AI first drafts an ad plan (music, voice-over script, sound effects), you can edit it, then generate the full ad with one click.",
    directorVoiceLabel: "Voice-over Voice (ElevenLabs)",
    directorStep1Btn: "1) Create Ad Plan",
    directorStep1Busy: "Preparing plan...",
    directorPlanTitle: "Ad Plan (editable)",
    directorTotalSecondsLabel: "Total duration (sec)",
    directorMusicPromptLabel: "Music Description",
    musicPreviewBtn: "🎧 Preview the Music First",
    musicPreviewBusy: "Generating music...",
    musicPreviewReadyLabel: "Music preview:",
    musicPreviewError: "Couldn't generate a music preview, try again.",
    directorVoiceoverLabel: "Voice-over Script",
    directorVoiceDelayLabel: "Voice-over delay (sec)",
    directorSfxTitle: "Sound Effects",
    directorSfxPromptLabel: "Effect description",
    directorSfxAtLabel: "At second",
    directorSfxDurationLabel: "Duration (sec)",
    directorSfxAddBtn: "+ Add Effect",
    directorSfxRemoveBtn: "Remove",
    directorSfxEmpty: "No effects.",
    directorNotesLabel: "Notes",
    directorStep2Btn: "2) Produce the Ad",
    directorStep2Busy: "Producing… (music+fx+voice+mix)",
    directorProduceNote:
      "Production can take 1-2 minutes — music, effects, and voice-over are generated in sequence, then merged.",
    directorResultTitle: "Final Ad Ready",
    directorResultSummaryTemplate: "Music + {n} effects + {sec}s voice-over",
    directorContinueBtn: "Continue to Create Campaign →",
    planRequiredError: "Create an ad plan first",
    steps: [
      "Target",
      "Spot Script",
      "Voice",
      "Jingle",
      "Merge Ad",
      "Summary + Confirm",
    ],
    cityLabel: "City (optional — leave blank for all cities)",
    cityPlaceholder: "e.g. Istanbul",
    daypartsLabel: "Dayparts",
    daypartLabels: {
      sabah: "Morning",
      gunduz: "Daytime",
      drive: "Drive-Time",
      aksam: "Evening",
      gece: "Night",
    } as Record<Daypart, string>,
    weeksLabel: "Number of weeks (1-12)",
    budgetLabel: "Budget (TRY)",
    budgetPlaceholder: "e.g. 5000",
    budgetRequiredError: "Enter a positive budget first",
    suggestBtn: "See Packages",
    suggestBusy: "Preparing packages...",
    packageLabels: {
      opening: "Opening Package",
      weekend: "Weekend Campaign",
      monthly: "1-Month Awareness",
    } as Record<"opening" | "weekend" | "monthly", string>,
    packageStations: "stations",
    packageWeeklySpots: "est. weekly spots",
    packageTotal: "total",
    packageEmpty: "No listings match these filters.",
    selectBtn: "Select This Package",
    selectedBtn: "Selected",
    customOption: "Custom: continue with my filters",
    customOptionNote: "Continues with the weeks and dayparts you entered.",
    productNameLabel: "Product / Artist name",
    productNamePlaceholder: "e.g. New album 'Midnight'",
    detailsLabel: "Details",
    detailsPlaceholder: "Key features, date, venue...",
    secondsLabel: "Duration",
    toneLabel: "Tone",
    toneLabels: {
      enerjik: "Energetic",
      samimi: "Warm",
      profesyonel: "Professional",
      eglenceli: "Playful",
    } as Record<(typeof TONE_OPTIONS)[number], string>,
    generateBtn: "Generate with AI",
    generateBusy: "Generating...",
    productNameRequiredError: "Enter the product/artist name first",
    scriptEditableLabel: "Spot script (editable)",
    scriptTemplateNote:
      "ANTHROPIC_API_KEY is not set — a template script was generated (still usable).",
    kuponNote:
      "The {KUPON} placeholder in the text is replaced with the real coupon code once the campaign is confirmed.",
    scriptRequiredError: "A spot script is required to continue",
    voiceStepTitle: "Voice-over (optional)",
    voiceStepNote:
      "You can skip this step — the radio station's own presenter can read the script too.",
    voicesLoading: "Loading voices...",
    voiceBtn: "Synthesize",
    voiceBusy: "Synthesizing...",
    audioReadyLabel: "Preview ready:",
    skipBtn: "Skip This Step",
    // --- Voice picker (VoiceLibraryPicker) ---
    voiceSearchPlaceholder: "Search voices (filter by name)...",
    voicesEmpty: "No voices match your search.",
    voiceListenLabel: "Listen",
    voiceSelectBtn: "Select",
    voiceSelectedBtn: "Selected",
    jingleStepTitle: "Jingle (optional)",
    autoJingleTitle: "AI Auto-Generated Jingle",
    autoJingleNote:
      "Generates a jingle matching the product/artist name and details from step 2 (Suno).",
    autoJingleBtn: "🎵 Generate a Jingle for My Script (AI)",
    autoJingleBusy: "Generating...",
    autoJingleGeneratingMsg: "Generating jingle, this may take a moment...",
    autoJingleReadyLabel: "Jingle preview ready:",
    orDivider: "— or —",
    jingleLibraryTitle: "Ready-Made Jingle Library",
    jingleLibraryEmpty: "No jingles ready right now.",
    jinglePreviewUnavailable: "Preview isn't available yet for this jingle.",
    jingleReadyTitle: "Custom jingle requests ready",
    selectJingleBtn: "Select This Jingle",
    selectedJingleBtn: "Selected",
    customJingleTitle: "Request a Custom Jingle",
    briefLabel: "Brief",
    briefPlaceholder: "Brand/product, message, desired mood...",
    styleLabel: "Style (optional)",
    stylePlaceholder: "e.g. acoustic, electronic, epic...",
    requestBtn: "Request Jingle",
    requestBusy: "Sending...",
    briefRequiredError: "Brief cannot be empty",
    jingleQueuedMsg:
      "Your request has been queued — it will be linked to your campaign once ready.",
    mixStepTitle: "Merge the Ad",
    mixStepDesc:
      "The music plays under the voice, and the ad fades out softly at the end — this is the finished spot ready to send to radio stations.",
    mixBtn: "🎬 Create the Ad (music + voice)",
    mixBusy: "Merging...",
    mixNeedVoiceError: "Generate a voice-over first (step 3)",
    mixNeedJingleError: "Select/generate a jingle first (step 4)",
    mixReadyLabel: "Finished ad:",
    mixDownloadBtn: "Download",
    summaryTitle: "Summary",
    summaryCity: "City",
    summaryCityAll: "All cities",
    summaryDayparts: "Dayparts",
    summaryDaypartsAll: "All dayparts",
    summaryWeeks: "Weeks",
    summaryBudget: "Budget",
    summaryProduct: "Product/Artist",
    summaryScript: "Spot script",
    summaryVoice: "Voice-over",
    summaryVoiceYes: "Ready (preview available)",
    summaryVoiceNo: "None — the station will read it live",
    summaryJingle: "Jingle",
    summaryJingleYes: "Selected",
    summaryJingleNo: "None",
    summaryMix: "Merged Ad",
    summaryMixYes: "Ready (downloadable)",
    summaryMixNo: "None",
    couponNote:
      "A unique coupon code is generated once the campaign is confirmed and added to the spot script.",
    commissionNote: "The total includes an 18% MuzikSEO commission.",
    buyerNameLabel: "Your name / Company",
    buyerNamePlaceholder: "Full name or company name",
    buyerEmailLabel: "Email",
    buyerKindLabel: "Buyer type",
    buyerKindLabels: { artist: "Artist", business: "Business" } as Record<
      BuyerKind,
      string
    >,
    buyerRequiredError: "Name and email are required",
    submitBtn: "Start Campaign",
    submitBusy: "Creating campaign...",
    backBtn: "Back",
    nextBtn: "Next",
    genericError: "Could not reach the server, try again.",
    successHeading: "Campaign created",
    campaignNoLabel: "Campaign No",
    couponLabel: "Coupon Code",
    totalLabel: "Total",
    trackingTitle: "Track Your Campaign",
    trackEmailLabel: "The email you used to create the campaign",
    checkStatusBtn: "Check Status",
    checkBusy: "Checking...",
    ordersTitle: "Order Breakdown",
    orderStatusLabels: {
      pending: "Pending",
      accepted: "Accepted",
      rejected: "Rejected",
      paid: "Paid",
      airing: "Airing",
    } as Record<AdCampaignOrderBreakdown["status"], string>,
    reportTitle: "Audit Report",
    plannedSpotsLabel: "Total planned spots",
    verifiedPlaysLabel: "Verified plays",
    perStationTitle: "Per-Station Breakdown",
    proofBtn: "Show Proof Logs",
    proofHideBtn: "Hide",
    proofLoading: "Loading proof logs...",
    proofEmpty: "No detections recorded yet.",
    proofScoreLabel: "match score",
    newCampaignBtn: "Start a New Campaign",
  },
} as const;

function statusPillClass(status: AdCampaignOrderBreakdown["status"]): string {
  if (status === "paid" || status === "airing") return "nb-pill nb-pill--green";
  if (status === "rejected") return "nb-pill nb-pill--red";
  if (status === "accepted") return "nb-pill nb-pill--purple";
  return "nb-pill nb-pill--blue";
}

type VoiceLibraryPickerTexts = {
  loadingLabel: string;
  emptyLabel: string;
  searchPlaceholder: string;
  listenLabel: string;
};

/** Sesi SECMEDEN ONCE dinleyebilme + arama + kaydirilabilir kompakt liste.
 *  Hem Reklam Yonetmeni'nde (plan sesi secimi) hem Adim-Adim'da (3. adim,
 *  secim = dogrudan seslendirme) kullanilir — "Sec" aksiyonu caller'dan
 *  renderAction ile gelir cunku iki modda farkli anlama gelir (sadece secim
 *  vs. hemen seslendirme uretimi). Tek <audio> ref'i: baska sese basinca
 *  oncekini durdurur (ayni anda tek ses calar). */
function VoiceLibraryPicker({
  voices,
  loading,
  texts,
  renderAction,
}: {
  voices: SpotVoice[] | null;
  loading: boolean;
  texts: VoiceLibraryPickerTexts;
  renderAction: (voice: SpotVoice) => ReactElement;
}) {
  const [query, setQuery] = useState("");
  const [playingId, setPlayingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
    };
  }, []);

  function togglePreview(voice: SpotVoice) {
    if (!voice.preview_url) return;
    const audio = audioRef.current ?? new Audio();
    if (!audioRef.current) {
      audio.onended = () => setPlayingId(null);
      audioRef.current = audio;
    }
    if (playingId === voice.voice_id) {
      audio.pause();
      setPlayingId(null);
      return;
    }
    audio.src = voice.preview_url;
    void audio.play();
    setPlayingId(voice.voice_id);
  }

  const needle = query.trim().toLowerCase();
  const filtered = (voices ?? []).filter((v) =>
    needle ? v.name.toLowerCase().includes(needle) : true
  );

  return (
    <div className={styles.voicePicker}>
      {loading && <div className={styles.note}>{texts.loadingLabel}</div>}
      <input
        className="nb-input"
        placeholder={texts.searchPlaceholder}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className={styles.voiceList}>
        {!loading && filtered.length === 0 && (
          <div className={styles.note}>{texts.emptyLabel}</div>
        )}
        {filtered.map((v) => {
          const labelBadges = v.labels ? Object.values(v.labels).filter(Boolean) : [];
          return (
            <div key={v.voice_id} className={styles.voiceRow}>
              <div className={styles.voiceRowInfo}>
                <span className={styles.voiceRowName}>{v.name}</span>
                <div className={styles.voiceRowBadges}>
                  {v.category && <span className="nb-chip">{v.category}</span>}
                  {labelBadges.slice(0, 3).map((label, i) => (
                    <span key={i} className="nb-chip">
                      {label}
                    </span>
                  ))}
                </div>
              </div>
              <div className={styles.voiceRowActions}>
                <button
                  type="button"
                  className="nb-btn nb-btn--outline"
                  onClick={() => togglePreview(v)}
                  disabled={!v.preview_url}
                  aria-label={texts.listenLabel}
                  title={texts.listenLabel}
                >
                  {playingId === v.voice_id ? "⏸" : "▶"}
                </button>
                {renderAction(v)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function CampaignWizardPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [step, setStep] = useState(1);
  // --- Mod secimi: yonetmen (tek-tik) vs adim adim -------------------------
  const [wizardMode, setWizardMode] = useState<WizardMode | null>(null);

  // --- Reklam Yonetmeni (tek-tik otomatik uretim) --------------------------
  const [directorPlan, setDirectorPlan] = useState<AdPlan | null>(null);
  const [directorPlanBusy, setDirectorPlanBusy] = useState(false);
  const [directorPlanError, setDirectorPlanError] = useState("");
  const [directorProduceBusy, setDirectorProduceBusy] = useState(false);
  const [directorProduceError, setDirectorProduceError] = useState("");
  const [directorResult, setDirectorResult] = useState<ProduceAdResult | null>(
    null
  );
  // --- Yonetmen: reklam uretilmeden once muzigi tek basina dinleme ----------
  const [musicPreviewBusy, setMusicPreviewBusy] = useState(false);
  const [musicPreviewError, setMusicPreviewError] = useState("");
  const [musicPreviewUrl, setMusicPreviewUrl] = useState<string | null>(null);

  // --- Adim 1: hedef -----------------------------------------------------
  const [city, setCity] = useState("");
  const [dayparts, setDayparts] = useState<Daypart[]>([]);
  const [weeks, setWeeks] = useState(2);
  const [budget, setBudget] = useState("");
  const [packages, setPackages] = useState<AdPackage[] | null>(null);
  const [packagesBusy, setPackagesBusy] = useState(false);
  const [packagesError, setPackagesError] = useState("");
  const [selectedPackageKey, setSelectedPackageKey] =
    useState<PackageKey | null>(null);

  // --- Adim 2: spot metni --------------------------------------------------
  const [productName, setProductName] = useState("");
  const [details, setDetails] = useState("");
  const [seconds, setSeconds] = useState<(typeof SECONDS_OPTIONS)[number]>(20);
  const [tone, setTone] = useState<(typeof TONE_OPTIONS)[number]>("enerjik");
  const [scriptBusy, setScriptBusy] = useState(false);
  const [scriptError, setScriptError] = useState("");
  const [scriptText, setScriptText] = useState("");
  const [scriptSource, setScriptSource] = useState<string | null>(null);

  // --- Adim 3: seslendirme (opsiyonel) -------------------------------------
  const [voices, setVoices] = useState<SpotVoice[] | null>(null);
  const [voicesLoading, setVoicesLoading] = useState(false);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string | null>(null);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [voiceAssetId, setVoiceAssetId] = useState<number | null>(null);

  // --- Adim 4: jingle (opsiyonel) -------------------------------------------
  const [jingleLibrary, setJingleLibrary] = useState<JingleLibraryItem[]>([]);
  const [readyJingles, setReadyJingles] = useState<JingleRequest[]>([]);
  const [jinglesLoaded, setJinglesLoaded] = useState(false);
  const [selectedJingleUrl, setSelectedJingleUrl] = useState<string | null>(
    null
  );
  /** Secili jingle bir talep kaydiysa (auto/hazir) id'si — mixAd'de
   *  jingle_request_id olarak gonderilir. Kutuphane dosyasi secilince null
   *  olur, o zaman jingle_file (selectedJingleUrl) kullanilir. */
  const [selectedJingleRequestId, setSelectedJingleRequestId] = useState<
    number | null
  >(null);
  const [jingleBrief, setJingleBrief] = useState("");
  const [jingleStyle, setJingleStyle] = useState("");
  const [jingleBusy, setJingleBusy] = useState(false);
  const [jingleMsg, setJingleMsg] = useState("");
  const [jingleError, setJingleError] = useState("");

  // --- Adim 4: AI otomatik jingle (Suno) -------------------------------------
  const [autoJingleBusy, setAutoJingleBusy] = useState(false);
  const [autoJingleError, setAutoJingleError] = useState("");
  const [autoJingleId, setAutoJingleId] = useState<number | null>(null);
  const [autoJingleStatus, setAutoJingleStatus] = useState<
    AutoJingle["status"] | null
  >(null);

  // --- Adim 5: reklami birlestir (mix) ---------------------------------------
  const [mixBusy, setMixBusy] = useState(false);
  const [mixError, setMixError] = useState("");
  const [mixAudioUrl, setMixAudioUrl] = useState<string | null>(null);
  const [mixAssetId, setMixAssetId] = useState<number | null>(null);

  // --- Adim 6: ozet + onay --------------------------------------------------
  const [buyerName, setBuyerName] = useState("");
  const [buyerEmail, setBuyerEmail] = useState("");
  const [buyerKind, setBuyerKind] = useState<BuyerKind>("artist");
  const [submitBusy, setSubmitBusy] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [campaign, setCampaign] = useState<AdCampaign | null>(null);

  // --- Kampanya takibi (basari sonrasi) --------------------------------------
  const [trackEmail, setTrackEmail] = useState("");
  const [trackBusy, setTrackBusy] = useState(false);
  const [trackError, setTrackError] = useState("");
  const [orders, setOrders] = useState<AdCampaignOrderBreakdown[] | null>(
    null
  );
  const [report, setReport] = useState<AdCampaignReport | null>(null);
  const [expandedOrderId, setExpandedOrderId] = useState<number | null>(null);
  const [proofByOrder, setProofByOrder] = useState<
    Record<number, FingerprintDetection[]>
  >({});
  const [proofBusy, setProofBusy] = useState<number | null>(null);

  useEffect(() => {
    const needsVoices =
      (wizardMode === "steps" && step === 3) || wizardMode === "director";
    if (needsVoices && voices === null && !voicesLoading) {
      setVoicesLoading(true);
      listSpotVoices().then((v) => {
        setVoices(v ?? []);
        setVoicesLoading(false);
      });
    }
  }, [step, wizardMode, voices, voicesLoading]);

  useEffect(() => {
    if (step === 4 && !jinglesLoaded) {
      listJingles().then((res) => {
        setJingleLibrary(res?.library ?? []);
        setReadyJingles(res?.ready_requests ?? []);
        setJinglesLoaded(true);
      });
    }
  }, [step, jinglesLoaded]);

  /** AI otomatik jingle uretimini ~5 sn'de bir yoklar; 'ready'/'failed' olunca
   *  durur. Component unmount olursa (veya id/status degisirse) interval
   *  temizlenir. */
  useEffect(() => {
    if (
      autoJingleId === null ||
      autoJingleStatus === "ready" ||
      autoJingleStatus === "failed"
    ) {
      return;
    }
    const interval = setInterval(async () => {
      const result = await pollJingle(autoJingleId);
      if (result.error || !result.data) {
        setAutoJingleStatus("failed");
        setAutoJingleError(result.error ?? t.genericError);
        return;
      }
      setAutoJingleStatus(result.data.status);
      if (result.data.status === "ready") {
        const url = jingleFileUrl(autoJingleId);
        setSelectedJingleUrl(url);
        setSelectedJingleRequestId(autoJingleId);
      } else if (result.data.status === "failed") {
        setAutoJingleError(result.data.error ?? t.genericError);
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [autoJingleId, autoJingleStatus, t.genericError]);

  function toggleDaypart(d: Daypart) {
    setDayparts((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]
    );
    setSelectedPackageKey(null);
  }

  function effectiveDayparts(): string[] {
    if (selectedPackageKey === "weekend") return ["drive", "aksam"];
    return dayparts;
  }

  function effectiveWeeks(): number {
    if (selectedPackageKey === "opening" || selectedPackageKey === "weekend")
      return 1;
    if (selectedPackageKey === "monthly") return 4;
    return weeks;
  }

  async function handleSuggestPackages() {
    setPackagesError("");
    const budgetNum = Number(budget);
    if (!budgetNum || budgetNum <= 0) {
      setPackagesError(t.budgetRequiredError);
      return;
    }
    setPackagesBusy(true);
    const result = await suggestAdPackages({
      city: city.trim() || undefined,
      budget_try: budgetNum,
      dayparts: dayparts.length ? dayparts : undefined,
    });
    setPackagesBusy(false);
    if (!result) {
      setPackagesError(t.genericError);
      return;
    }
    setPackages(result);
    setSelectedPackageKey(null);
  }

  async function handleGenerateScript() {
    setScriptError("");
    if (!productName.trim()) {
      setScriptError(t.productNameRequiredError);
      return;
    }
    setScriptBusy(true);
    const result = await generateSpotScript({
      product_name: productName.trim(),
      details: details.trim(),
      seconds,
      tone,
    });
    setScriptBusy(false);
    if (result.error || !result.data) {
      setScriptError(result.error ?? t.genericError);
      return;
    }
    setScriptText(result.data.text);
    setScriptSource(result.data.source);
  }

  /** Yonetmen modu adim 1: urun/detay/ton/sureden tam bir reklam plani
   *  cikarir (muzik + seslendirme metni + efektler). Sonuc duzenlenebilir. */
  async function handleGeneratePlan() {
    setDirectorPlanError("");
    setDirectorResult(null);
    setMusicPreviewUrl(null);
    setMusicPreviewError("");
    if (!productName.trim()) {
      setDirectorPlanError(t.productNameRequiredError);
      return;
    }
    setDirectorPlanBusy(true);
    const result = await planAd({
      product_name: productName.trim(),
      details: details.trim() || undefined,
      tone,
      seconds,
    });
    setDirectorPlanBusy(false);
    if (result.error || !result.data) {
      setDirectorPlanError(result.error ?? t.genericError);
      return;
    }
    setDirectorPlan(result.data);
    // Adim-adim moda gecilirse spot metni zaten dolu olsun diye senkronlanir.
    setScriptText(result.data.voiceover);
  }

  /** Tam reklam uretilmeden ONCE sadece muzigi (plan.music_prompt) dinlemeyi
   *  saglar — kullanici begenmezse metni duzenleyip tekrar dinleyebilir. */
  async function handleMusicPreview() {
    if (!directorPlan) return;
    setMusicPreviewError("");
    setMusicPreviewBusy(true);
    const result = await makeMusic({
      prompt: directorPlan.music_prompt,
      seconds: directorPlan.total_seconds,
    });
    setMusicPreviewBusy(false);
    if (result.error || !result.data) {
      setMusicPreviewError(result.error ?? t.musicPreviewError);
      return;
    }
    setMusicPreviewUrl(apiFileUrl(result.data.file_url));
  }

  function updatePlanField<K extends keyof AdPlan>(key: K, value: AdPlan[K]) {
    setDirectorPlan((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function updateSfxField(
    index: number,
    field: keyof AdPlanSfx,
    value: string | number
  ) {
    setDirectorPlan((prev) => {
      if (!prev) return prev;
      const sfx = prev.sfx.map((s, i) =>
        i === index ? { ...s, [field]: value } : s
      );
      return { ...prev, sfx };
    });
  }

  function addSfxRow() {
    setDirectorPlan((prev) =>
      prev
        ? { ...prev, sfx: [...prev.sfx, { prompt: "", at_second: 0, duration: 1 }] }
        : prev
    );
  }

  function removeSfxRow(index: number) {
    setDirectorPlan((prev) =>
      prev ? { ...prev, sfx: prev.sfx.filter((_, i) => i !== index) } : prev
    );
  }

  /** Yonetmen modu adim 2: (duzenlenmis) plani tek cagride tam reklama
   *  cevirir. Basarili olunca mixAudioUrl/mixAssetId sihirbazin geri kalanina
   *  (kampanya olusturma) baglanir — kullanici adim-adim moda gecerse hazir. */
  async function handleProduceAd() {
    if (!directorPlan) {
      setDirectorProduceError(t.planRequiredError);
      return;
    }
    setDirectorProduceError("");
    setDirectorProduceBusy(true);
    const result = await produceAd({
      plan: directorPlan,
      voice_id: selectedVoiceId ?? undefined,
      campaign_hint: productName.trim() || undefined,
    });
    setDirectorProduceBusy(false);
    if (result.error || !result.data) {
      setDirectorProduceError(result.error ?? t.genericError);
      return;
    }
    setDirectorResult(result.data);
    setMixAudioUrl(apiFileUrl(result.data.mix_file_url));
    setMixAssetId(result.data.mix.id);
  }

  /** Yonetmen sonucundan adim-adim moda gecip kampanya olusturmaya devam
   *  eder — hedef (sehir/butce/kusak) secimi icin 1. adimdan baslar; urun
   *  adi/spot metni/mix zaten dolu oldugundan sonraki adimlar hizli gecilir. */
  function continueToCampaign() {
    setWizardMode("steps");
    setStep(1);
  }

  async function handleSynthesize(voiceId: string) {
    if (!scriptText.trim()) return;
    setSelectedVoiceId(voiceId);
    setVoiceError("");
    setVoiceBusy(true);
    const result = await synthesizeSpotVoice({
      text: scriptText.trim(),
      voice_id: voiceId,
    });
    setVoiceBusy(false);
    if (result.error || !result.data) {
      setVoiceError(result.error ?? t.genericError);
      return;
    }
    setAudioUrl(result.data.full_url);
    setVoiceAssetId(result.data.asset.id);
  }

  function selectLibraryJingle(item: JingleLibraryItem) {
    const isSame = selectedJingleUrl === item.path;
    setSelectedJingleUrl(isSame ? null : item.path);
    setSelectedJingleRequestId(null);
  }

  function selectReadyJingle(item: JingleRequest) {
    if (!item.file_path) return;
    const isSame = selectedJingleUrl === item.file_path;
    setSelectedJingleUrl(isSame ? null : item.file_path);
    setSelectedJingleRequestId(isSame ? null : item.id);
  }

  /** AI ile senaryoya (2. adimdaki urun/detay/ton) uygun jingle uretimini
   *  baslatir; sonuc pollJingle useEffect'i tarafindan izlenir. */
  async function handleAutoJingle() {
    setAutoJingleError("");
    setAutoJingleBusy(true);
    const result = await autoJingle({
      product_name: productName.trim() || undefined,
      details: details.trim() || undefined,
      tone,
      seconds,
    });
    setAutoJingleBusy(false);
    if (result.error || !result.data) {
      setAutoJingleError(result.error ?? t.genericError);
      return;
    }
    setAutoJingleId(result.data.id);
    setAutoJingleStatus(result.data.status);
  }

  async function handleRequestJingle() {
    setJingleError("");
    setJingleMsg("");
    if (!jingleBrief.trim()) {
      setJingleError(t.briefRequiredError);
      return;
    }
    setJingleBusy(true);
    const result = await requestJingle({
      brief: jingleBrief.trim(),
      style: jingleStyle.trim() || undefined,
    });
    setJingleBusy(false);
    if (result.error || !result.data) {
      setJingleError(result.error ?? t.genericError);
      return;
    }
    setJingleMsg(t.jingleQueuedMsg);
    setJingleBrief("");
    setJingleStyle("");
  }

  /** Seslendirme (3. adim) + secili jingle'i (4. adim) tek reklam dosyasinda
   *  birlestirir. Ikisi de sart — eksikse Turkce uyari gosterip cikar. */
  async function handleMixAd() {
    setMixError("");
    if (!voiceAssetId) {
      setMixError(t.mixNeedVoiceError);
      return;
    }
    if (!selectedJingleRequestId && !selectedJingleUrl) {
      setMixError(t.mixNeedJingleError);
      return;
    }
    setMixBusy(true);
    const payload: {
      voice_asset_id: number;
      jingle_request_id?: number;
      jingle_file?: string;
      campaign_hint?: string;
    } = { voice_asset_id: voiceAssetId };
    if (selectedJingleRequestId) {
      payload.jingle_request_id = selectedJingleRequestId;
    } else if (selectedJingleUrl) {
      payload.jingle_file = selectedJingleUrl;
    }
    if (productName.trim()) payload.campaign_hint = productName.trim();

    const result = await mixAd(payload);
    setMixBusy(false);
    if (result.error || !result.data) {
      setMixError(result.error ?? t.genericError);
      return;
    }
    setMixAudioUrl(apiFileUrl(result.data.file_url));
    setMixAssetId(result.data.asset.id);
  }

  async function handleSubmitCampaign(e: FormEvent) {
    e.preventDefault();
    if (submitBusy) return;
    setSubmitError("");
    if (!buyerName.trim() || !buyerEmail.trim()) {
      setSubmitError(t.buyerRequiredError);
      return;
    }
    setSubmitBusy(true);
    const result = await createAdCampaign({
      buyer_name: buyerName.trim(),
      buyer_email: buyerEmail.trim(),
      buyer_kind: buyerKind,
      product_name: productName.trim(),
      spot_text: scriptText.trim(),
      cities: city.trim() ? [city.trim()] : [],
      dayparts: effectiveDayparts(),
      weeks: effectiveWeeks(),
      budget_try: Number(budget) || 0,
      // Birlestirilmis reklam varsa (muzik + ses) o gonderilir — radyoya
      // yayinlanacak hazir spot budur; yoksa sadece seslendirmeye duser.
      audio_url: mixAudioUrl ?? audioUrl ?? undefined,
      jingle_url: selectedJingleUrl ?? undefined,
    });
    setSubmitBusy(false);
    if (result.error || !result.data) {
      setSubmitError(result.error ?? t.genericError);
      return;
    }
    setCampaign(result.data);
    setTrackEmail(result.data.buyer_email);
  }

  async function handleCheckStatus() {
    if (!campaign || !trackEmail.trim()) return;
    setTrackError("");
    setTrackBusy(true);
    const statusResult = await getAdCampaign(campaign.id, trackEmail.trim());
    if (statusResult.error || !statusResult.data) {
      setTrackBusy(false);
      setTrackError(statusResult.error ?? t.genericError);
      return;
    }
    setOrders(statusResult.data.orders);
    const reportResult = await getAdCampaignReport(
      campaign.id,
      trackEmail.trim()
    );
    setTrackBusy(false);
    if (reportResult.data) setReport(reportResult.data);
  }

  async function handleToggleProof(orderId: number) {
    if (expandedOrderId === orderId) {
      setExpandedOrderId(null);
      return;
    }
    setExpandedOrderId(orderId);
    if (!proofByOrder[orderId]) {
      setProofBusy(orderId);
      const detections = await getCampaignProof(orderId);
      setProofByOrder((prev) => ({ ...prev, [orderId]: detections ?? [] }));
      setProofBusy(null);
    }
  }

  function resetWizard() {
    setStep(1);
    setWizardMode(null);
    setDirectorPlan(null);
    setDirectorPlanError("");
    setDirectorProduceError("");
    setDirectorResult(null);
    setMusicPreviewBusy(false);
    setMusicPreviewError("");
    setMusicPreviewUrl(null);
    setCity("");
    setDayparts([]);
    setWeeks(2);
    setBudget("");
    setPackages(null);
    setSelectedPackageKey(null);
    setProductName("");
    setDetails("");
    setScriptText("");
    setScriptSource(null);
    setVoices(null);
    setSelectedVoiceId(null);
    setAudioUrl(null);
    setVoiceAssetId(null);
    setJinglesLoaded(false);
    setSelectedJingleUrl(null);
    setSelectedJingleRequestId(null);
    setAutoJingleBusy(false);
    setAutoJingleError("");
    setAutoJingleId(null);
    setAutoJingleStatus(null);
    setMixBusy(false);
    setMixError("");
    setMixAudioUrl(null);
    setMixAssetId(null);
    setBuyerName("");
    setBuyerEmail("");
    setCampaign(null);
    setOrders(null);
    setReport(null);
    setExpandedOrderId(null);
    setProofByOrder({});
  }

  const canAdvanceStep1 = selectedPackageKey !== null;
  const canAdvanceStep2 = scriptText.trim().length > 0;

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" className={styles.logo}>
            {t.logo}
          </Link>
          <LangToggle />
        </div>
        {!campaign && wizardMode !== null && (
          <button
            type="button"
            className="nb-btn nb-btn--outline"
            onClick={() => setWizardMode(null)}
          >
            {t.backToModesBtn}
          </button>
        )}
      </div>

      <h1 className="nb-h">{t.heading}</h1>
      <p className={styles.intro}>{t.intro}</p>

      {!campaign && wizardMode === null && (
        <div className={`nb-card ${styles.panel}`}>
          <h2 className="nb-h">{t.modeChooserTitle}</h2>
          <div className={styles.modeGrid}>
            <button
              type="button"
              className={`nb-card ${styles.modeCard} ${styles.modeCardDirector}`}
              onClick={() => setWizardMode("director")}
            >
              <div className={styles.modeTitle}>{t.directorModeTitle}</div>
              <p className={styles.modeDesc}>{t.directorModeDesc}</p>
            </button>
            <button
              type="button"
              className={`nb-card ${styles.modeCard}`}
              onClick={() => setWizardMode("steps")}
            >
              <div className={styles.modeTitle}>{t.stepModeTitle}</div>
              <p className={styles.modeDesc}>{t.stepModeDesc}</p>
            </button>
          </div>
        </div>
      )}

      {!campaign && wizardMode === "director" && (
        <div className={`nb-card ${styles.panel}`}>
          <h2 className="nb-h">{t.directorHeading}</h2>
          <p className={styles.note}>{t.directorIntro}</p>

          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>{t.productNameLabel}</label>
            <input
              className="nb-input"
              placeholder={t.productNamePlaceholder}
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
            />
          </div>
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>{t.detailsLabel}</label>
            <textarea
              className={`nb-input ${styles.textarea}`}
              placeholder={t.detailsPlaceholder}
              value={details}
              onChange={(e) => setDetails(e.target.value)}
            />
          </div>

          <div className={styles.rowFields}>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>{t.toneLabel}</label>
              <div className={styles.chipRow}>
                {TONE_OPTIONS.map((tn) => (
                  <button
                    key={tn}
                    type="button"
                    className={`${styles.chip} ${
                      tone === tn ? styles.chipActive : ""
                    }`}
                    onClick={() => setTone(tn)}
                  >
                    {t.toneLabels[tn]}
                  </button>
                ))}
              </div>
            </div>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>{t.secondsLabel}</label>
              <div className={styles.chipRow}>
                {SECONDS_OPTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className={`${styles.chip} ${
                      seconds === s ? styles.chipActive : ""
                    }`}
                    onClick={() => setSeconds(s)}
                  >
                    {s} sn
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>{t.directorVoiceLabel}</label>
            <VoiceLibraryPicker
              voices={voices}
              loading={voicesLoading}
              texts={{
                loadingLabel: t.voicesLoading,
                emptyLabel: t.voicesEmpty,
                searchPlaceholder: t.voiceSearchPlaceholder,
                listenLabel: t.voiceListenLabel,
              }}
              renderAction={(v) => (
                <button
                  type="button"
                  className={`nb-btn ${
                    selectedVoiceId === v.voice_id ? "nb-btn--green" : ""
                  }`}
                  onClick={() =>
                    setSelectedVoiceId(
                      selectedVoiceId === v.voice_id ? null : v.voice_id
                    )
                  }
                >
                  {selectedVoiceId === v.voice_id
                    ? t.voiceSelectedBtn
                    : t.voiceSelectBtn}
                </button>
              )}
            />
          </div>

          <button
            type="button"
            className="nb-btn nb-btn--purple"
            onClick={handleGeneratePlan}
            disabled={directorPlanBusy}
          >
            {directorPlanBusy ? t.directorStep1Busy : t.directorStep1Btn}
          </button>
          {directorPlanError && (
            <div className={styles.error}>{directorPlanError}</div>
          )}

          {directorPlan && (
            <div className={styles.summaryBox}>
              <h3 className={styles.subheading}>{t.directorPlanTitle}</h3>

              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>
                  {t.directorTotalSecondsLabel}
                </label>
                <input
                  className="nb-input"
                  type="number"
                  min={1}
                  value={directorPlan.total_seconds}
                  onChange={(e) =>
                    updatePlanField(
                      "total_seconds",
                      Number(e.target.value) || 0
                    )
                  }
                />
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>
                  {t.directorMusicPromptLabel}
                </label>
                <input
                  className="nb-input"
                  value={directorPlan.music_prompt}
                  onChange={(e) => {
                    updatePlanField("music_prompt", e.target.value);
                    setMusicPreviewUrl(null);
                  }}
                />
                <button
                  type="button"
                  className="nb-btn nb-btn--outline"
                  onClick={handleMusicPreview}
                  disabled={musicPreviewBusy || !directorPlan.music_prompt.trim()}
                >
                  {musicPreviewBusy ? t.musicPreviewBusy : t.musicPreviewBtn}
                </button>
                {musicPreviewError && (
                  <div className={styles.error}>{musicPreviewError}</div>
                )}
                {musicPreviewUrl && (
                  <div className={styles.audioBox}>
                    <span>{t.musicPreviewReadyLabel}</span>
                    <audio
                      controls
                      src={musicPreviewUrl}
                      className={styles.audioPlayer}
                    />
                  </div>
                )}
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>
                  {t.directorVoiceoverLabel}
                </label>
                <textarea
                  className={`nb-input ${styles.scriptTextarea}`}
                  value={directorPlan.voiceover}
                  onChange={(e) =>
                    updatePlanField("voiceover", e.target.value)
                  }
                />
                <p className={styles.note}>{t.kuponNote}</p>
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>
                  {t.directorVoiceDelayLabel}
                </label>
                <input
                  className="nb-input"
                  type="number"
                  min={0}
                  value={directorPlan.voice_delay_seconds}
                  onChange={(e) =>
                    updatePlanField(
                      "voice_delay_seconds",
                      Number(e.target.value) || 0
                    )
                  }
                />
              </div>

              <h4 className={styles.subheading}>{t.directorSfxTitle}</h4>
              {directorPlan.sfx.length === 0 && (
                <p className={styles.note}>{t.directorSfxEmpty}</p>
              )}
              {directorPlan.sfx.map((s, i) => (
                <div key={i} className={styles.rowFields}>
                  <div className={styles.fieldGroup}>
                    <label className={styles.fieldLabel}>
                      {t.directorSfxPromptLabel}
                    </label>
                    <input
                      className="nb-input"
                      value={s.prompt}
                      onChange={(e) =>
                        updateSfxField(i, "prompt", e.target.value)
                      }
                    />
                  </div>
                  <div className={styles.fieldGroup}>
                    <label className={styles.fieldLabel}>
                      {t.directorSfxAtLabel}
                    </label>
                    <input
                      className="nb-input"
                      type="number"
                      min={0}
                      value={s.at_second}
                      onChange={(e) =>
                        updateSfxField(
                          i,
                          "at_second",
                          Number(e.target.value) || 0
                        )
                      }
                    />
                  </div>
                  <div className={styles.fieldGroup}>
                    <label className={styles.fieldLabel}>
                      {t.directorSfxDurationLabel}
                    </label>
                    <input
                      className="nb-input"
                      type="number"
                      min={0}
                      value={s.duration}
                      onChange={(e) =>
                        updateSfxField(
                          i,
                          "duration",
                          Number(e.target.value) || 0
                        )
                      }
                    />
                  </div>
                  <button
                    type="button"
                    className="nb-btn nb-btn--outline"
                    onClick={() => removeSfxRow(i)}
                  >
                    {t.directorSfxRemoveBtn}
                  </button>
                </div>
              ))}
              <button type="button" className="nb-btn" onClick={addSfxRow}>
                {t.directorSfxAddBtn}
              </button>

              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>
                  {t.directorNotesLabel}
                </label>
                <p className={styles.note}>{directorPlan.notes}</p>
              </div>

              <button
                type="button"
                className="nb-btn nb-btn--green"
                onClick={handleProduceAd}
                disabled={directorProduceBusy}
              >
                {directorProduceBusy
                  ? t.directorStep2Busy
                  : t.directorStep2Btn}
              </button>
              {directorProduceBusy && (
                <div className={styles.note}>{t.directorProduceNote}</div>
              )}
              {directorProduceError && (
                <div className={styles.error}>{directorProduceError}</div>
              )}

              {directorResult && mixAudioUrl && (
                <div className={styles.audioBox}>
                  <span>{t.directorResultTitle}</span>
                  <audio
                    controls
                    src={mixAudioUrl}
                    className={styles.audioPlayer}
                  />
                  <a
                    href={mixAudioUrl}
                    download
                    className="nb-btn nb-btn--outline"
                  >
                    {t.mixDownloadBtn}
                  </a>
                  <span className="nb-chip">
                    {t.directorResultSummaryTemplate
                      .replace("{n}", String(directorResult.sfx.length))
                      .replace(
                        "{sec}",
                        String(directorResult.voice.duration ?? "?")
                      )}
                  </span>
                  <button
                    type="button"
                    className="nb-btn nb-btn--green"
                    onClick={continueToCampaign}
                  >
                    {t.directorContinueBtn}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {!campaign && wizardMode === "steps" && (
        <div className={styles.stepper}>
          {t.steps.map((label, i) => {
            const idx = i + 1;
            const done = idx < step;
            const active = idx === step;
            return (
              <div
                key={label}
                className={`${styles.stepItem} ${
                  active ? styles.stepItemActive : ""
                } ${done ? styles.stepItemDone : ""}`}
              >
                <span className={styles.stepNumber}>{idx}</span>
                <span className={styles.stepLabel}>{label}</span>
              </div>
            );
          })}
        </div>
      )}

      {!campaign && wizardMode === "steps" && step === 1 && (
        <div className={`nb-card ${styles.panel}`}>
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>{t.cityLabel}</label>
            <input
              className="nb-input"
              placeholder={t.cityPlaceholder}
              value={city}
              onChange={(e) => {
                setCity(e.target.value);
                setSelectedPackageKey(null);
              }}
            />
          </div>

          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>{t.daypartsLabel}</label>
            <div className={styles.chipRow}>
              {DAYPARTS.map((d) => (
                <button
                  key={d}
                  type="button"
                  className={`${styles.chip} ${
                    dayparts.includes(d) ? styles.chipActive : ""
                  }`}
                  onClick={() => toggleDaypart(d)}
                >
                  {t.daypartLabels[d]}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.rowFields}>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>{t.weeksLabel}</label>
              <input
                className="nb-input"
                type="number"
                min={1}
                max={12}
                value={weeks}
                onChange={(e) => {
                  setWeeks(Math.min(12, Math.max(1, Number(e.target.value) || 1)));
                  setSelectedPackageKey(null);
                }}
              />
            </div>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>{t.budgetLabel}</label>
              <input
                className="nb-input"
                type="number"
                min={0}
                placeholder={t.budgetPlaceholder}
                value={budget}
                onChange={(e) => {
                  setBudget(e.target.value);
                  setSelectedPackageKey(null);
                }}
              />
            </div>
          </div>

          <button
            type="button"
            className="nb-btn"
            onClick={handleSuggestPackages}
            disabled={packagesBusy}
          >
            {packagesBusy ? t.suggestBusy : t.suggestBtn}
          </button>
          {packagesError && <div className={styles.error}>{packagesError}</div>}

          {packages && (
            <div className={styles.packageGrid}>
              {packages.map((pkg) => (
                <div
                  key={pkg.key}
                  className={`nb-card ${styles.packageCard} ${
                    selectedPackageKey === pkg.key ? styles.packageCardActive : ""
                  }`}
                >
                  <div className={styles.packageLabel}>
                    {t.packageLabels[pkg.key]}
                  </div>
                  <div className={styles.packageStats}>
                    <span className="nb-chip">
                      {pkg.listings.length} {t.packageStations}
                    </span>
                    <span className="nb-chip">
                      {pkg.est_weekly_spots} {t.packageWeeklySpots}
                    </span>
                  </div>
                  <div className={styles.packageTotal}>
                    {pkg.total_try} TL <span>{t.packageTotal}</span>
                  </div>
                  {pkg.listings.length === 0 ? (
                    <div className={styles.packageEmpty}>{t.packageEmpty}</div>
                  ) : (
                    <button
                      type="button"
                      className={`nb-btn ${
                        selectedPackageKey === pkg.key ? "nb-btn--green" : ""
                      }`}
                      onClick={() => setSelectedPackageKey(pkg.key)}
                    >
                      {selectedPackageKey === pkg.key ? t.selectedBtn : t.selectBtn}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {packages && (
            <div className={styles.customOptionBox}>
              <button
                type="button"
                className={`nb-btn nb-btn--outline ${
                  selectedPackageKey === "custom" ? styles.customActive : ""
                }`}
                onClick={() => setSelectedPackageKey("custom")}
              >
                {selectedPackageKey === "custom" ? t.selectedBtn : t.customOption}
              </button>
              <p className={styles.customOptionNote}>{t.customOptionNote}</p>
            </div>
          )}

          <div className={styles.navRow}>
            <span />
            <button
              type="button"
              className="nb-btn"
              disabled={!canAdvanceStep1}
              onClick={() => setStep(2)}
            >
              {t.nextBtn}
            </button>
          </div>
        </div>
      )}

      {!campaign && wizardMode === "steps" && step === 2 && (
        <div className={`nb-card ${styles.panel}`}>
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>{t.productNameLabel}</label>
            <input
              className="nb-input"
              placeholder={t.productNamePlaceholder}
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
            />
          </div>
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>{t.detailsLabel}</label>
            <textarea
              className={`nb-input ${styles.textarea}`}
              placeholder={t.detailsPlaceholder}
              value={details}
              onChange={(e) => setDetails(e.target.value)}
            />
          </div>

          <div className={styles.rowFields}>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>{t.secondsLabel}</label>
              <div className={styles.chipRow}>
                {SECONDS_OPTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className={`${styles.chip} ${
                      seconds === s ? styles.chipActive : ""
                    }`}
                    onClick={() => setSeconds(s)}
                  >
                    {s} sn
                  </button>
                ))}
              </div>
            </div>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>{t.toneLabel}</label>
              <div className={styles.chipRow}>
                {TONE_OPTIONS.map((tn) => (
                  <button
                    key={tn}
                    type="button"
                    className={`${styles.chip} ${
                      tone === tn ? styles.chipActive : ""
                    }`}
                    onClick={() => setTone(tn)}
                  >
                    {t.toneLabels[tn]}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <button
            type="button"
            className="nb-btn nb-btn--purple"
            onClick={handleGenerateScript}
            disabled={scriptBusy}
          >
            {scriptBusy ? t.generateBusy : t.generateBtn}
          </button>
          {scriptError && <div className={styles.error}>{scriptError}</div>}

          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>{t.scriptEditableLabel}</label>
            <textarea
              className={`nb-input ${styles.scriptTextarea}`}
              value={scriptText}
              onChange={(e) => setScriptText(e.target.value)}
            />
            {scriptSource === "template" && (
              <p className={styles.note}>{t.scriptTemplateNote}</p>
            )}
            <p className={styles.note}>{t.kuponNote}</p>
          </div>

          <div className={styles.navRow}>
            <button type="button" className="nb-btn nb-btn--outline" onClick={() => setStep(1)}>
              {t.backBtn}
            </button>
            <button
              type="button"
              className="nb-btn"
              disabled={!canAdvanceStep2}
              onClick={() => setStep(3)}
              title={!canAdvanceStep2 ? t.scriptRequiredError : undefined}
            >
              {t.nextBtn}
            </button>
          </div>
        </div>
      )}

      {!campaign && wizardMode === "steps" && step === 3 && (
        <div className={`nb-card ${styles.panel}`}>
          <h2 className="nb-h">{t.voiceStepTitle}</h2>
          <p className={styles.note}>{t.voiceStepNote}</p>

          <VoiceLibraryPicker
            voices={voices}
            loading={voicesLoading}
            texts={{
              loadingLabel: t.voicesLoading,
              emptyLabel: t.voicesEmpty,
              searchPlaceholder: t.voiceSearchPlaceholder,
              listenLabel: t.voiceListenLabel,
            }}
            renderAction={(v) => (
              <button
                type="button"
                className={`nb-btn ${
                  selectedVoiceId === v.voice_id && audioUrl ? "nb-btn--green" : ""
                }`}
                disabled={voiceBusy && selectedVoiceId === v.voice_id}
                onClick={() => handleSynthesize(v.voice_id)}
              >
                {voiceBusy && selectedVoiceId === v.voice_id
                  ? t.voiceBusy
                  : t.voiceBtn}
              </button>
            )}
          />

          {voiceError && <div className={styles.error}>{voiceError}</div>}

          {audioUrl && (
            <div className={styles.audioBox}>
              <span>{t.audioReadyLabel}</span>
              <audio controls src={audioUrl} className={styles.audioPlayer} />
            </div>
          )}

          <div className={styles.navRow}>
            <button type="button" className="nb-btn nb-btn--outline" onClick={() => setStep(2)}>
              {t.backBtn}
            </button>
            <button type="button" className="nb-btn" onClick={() => setStep(4)}>
              {audioUrl ? t.nextBtn : t.skipBtn}
            </button>
          </div>
        </div>
      )}

      {!campaign && wizardMode === "steps" && step === 4 && (
        <div className={`nb-card ${styles.panel}`}>
          <h2 className="nb-h">{t.jingleStepTitle}</h2>

          <h3 className={styles.subheading}>{t.autoJingleTitle}</h3>
          <p className={styles.note}>{t.autoJingleNote}</p>
          <button
            type="button"
            className="nb-btn nb-btn--purple"
            onClick={handleAutoJingle}
            disabled={autoJingleBusy || autoJingleStatus === "generating"}
          >
            {autoJingleBusy || autoJingleStatus === "generating"
              ? t.autoJingleBusy
              : t.autoJingleBtn}
          </button>
          {(autoJingleStatus === "generating" ||
            autoJingleStatus === "queued") && (
            <div className={styles.note}>{t.autoJingleGeneratingMsg}</div>
          )}
          {autoJingleError && (
            <div className={styles.error}>{autoJingleError}</div>
          )}
          {autoJingleStatus === "ready" && autoJingleId !== null && (
            <div className={styles.audioBox}>
              <span>{t.autoJingleReadyLabel}</span>
              <audio
                controls
                src={jingleFileUrl(autoJingleId)}
                className={styles.audioPlayer}
              />
            </div>
          )}

          <p className={styles.note} style={{ textAlign: "center" }}>
            {t.orDivider}
          </p>

          <h3 className={styles.subheading}>{t.jingleLibraryTitle}</h3>
          {jingleLibrary.length === 0 ? (
            <p className={styles.note}>{t.jingleLibraryEmpty}</p>
          ) : (
            <div className={styles.jingleGrid}>
              {jingleLibrary.map((item) => (
                <div key={item.path} className={`nb-card ${styles.jingleCard}`}>
                  <div className={styles.jingleName}>{item.file_name}</div>
                  {/* Kutuphane dosyalari sunucuda ham dosya yolu olarak
                      tutuluyor (data/jingles/*.mp3) — henuz HTTP uzerinden
                      tek tek servis eden bir uc nokta yok, o yuzden dinleme
                      butonu burada pasif kalir (bkz. selectedJingleBtn
                      secimi hala calisir, mix asamasinda sunucu tarafinda
                      dogrudan dosyadan okunur). */}
                  <button
                    type="button"
                    className="nb-btn nb-btn--outline"
                    disabled
                    title={t.jinglePreviewUnavailable}
                    aria-label={t.jinglePreviewUnavailable}
                  >
                    ▶
                  </button>
                  <button
                    type="button"
                    className={`nb-btn ${
                      selectedJingleUrl === item.path ? "nb-btn--green" : ""
                    }`}
                    onClick={() => selectLibraryJingle(item)}
                  >
                    {selectedJingleUrl === item.path
                      ? t.selectedJingleBtn
                      : t.selectJingleBtn}
                  </button>
                </div>
              ))}
            </div>
          )}

          {readyJingles.length > 0 && (
            <>
              <h3 className={styles.subheading}>{t.jingleReadyTitle}</h3>
              <div className={styles.jingleGrid}>
                {readyJingles.map((item) => (
                  <div key={item.id} className={`nb-card ${styles.jingleCard}`}>
                    <div className={styles.jingleName}>{item.brief}</div>
                    {item.style && <span className="nb-chip">{item.style}</span>}
                    {item.file_path && (
                      <audio
                        controls
                        src={jingleFileUrl(item.id)}
                        className={styles.audioPlayer}
                      />
                    )}
                    <button
                      type="button"
                      className={`nb-btn ${
                        selectedJingleUrl === item.file_path ? "nb-btn--green" : ""
                      }`}
                      onClick={() => selectReadyJingle(item)}
                    >
                      {selectedJingleUrl === item.file_path
                        ? t.selectedJingleBtn
                        : t.selectJingleBtn}
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}

          <h3 className={styles.subheading}>{t.customJingleTitle}</h3>
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>{t.briefLabel}</label>
            <textarea
              className={`nb-input ${styles.textarea}`}
              placeholder={t.briefPlaceholder}
              value={jingleBrief}
              onChange={(e) => setJingleBrief(e.target.value)}
            />
          </div>
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>{t.styleLabel}</label>
            <input
              className="nb-input"
              placeholder={t.stylePlaceholder}
              value={jingleStyle}
              onChange={(e) => setJingleStyle(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="nb-btn nb-btn--purple"
            onClick={handleRequestJingle}
            disabled={jingleBusy}
          >
            {jingleBusy ? t.requestBusy : t.requestBtn}
          </button>
          {jingleError && <div className={styles.error}>{jingleError}</div>}
          {jingleMsg && <div className={styles.successBox}>{jingleMsg}</div>}

          <div className={styles.navRow}>
            <button type="button" className="nb-btn nb-btn--outline" onClick={() => setStep(3)}>
              {t.backBtn}
            </button>
            <button type="button" className="nb-btn" onClick={() => setStep(5)}>
              {selectedJingleUrl ? t.nextBtn : t.skipBtn}
            </button>
          </div>
        </div>
      )}

      {!campaign && wizardMode === "steps" && step === 5 && (
        <div className={`nb-card ${styles.panel}`}>
          <h2 className="nb-h">{t.mixStepTitle}</h2>
          <p className={styles.note}>{t.mixStepDesc}</p>

          {!voiceAssetId && (
            <div className={styles.note}>{t.mixNeedVoiceError}</div>
          )}
          {voiceAssetId && !selectedJingleRequestId && !selectedJingleUrl && (
            <div className={styles.note}>{t.mixNeedJingleError}</div>
          )}

          <button
            type="button"
            className="nb-btn nb-btn--purple"
            onClick={handleMixAd}
            disabled={
              mixBusy ||
              !voiceAssetId ||
              (!selectedJingleRequestId && !selectedJingleUrl)
            }
          >
            {mixBusy ? t.mixBusy : t.mixBtn}
          </button>
          {mixError && <div className={styles.error}>{mixError}</div>}

          {mixAudioUrl && (
            <div className={styles.audioBox}>
              <span>{t.mixReadyLabel}</span>
              <audio controls src={mixAudioUrl} className={styles.audioPlayer} />
              <a
                href={mixAudioUrl}
                download
                className="nb-btn nb-btn--outline"
              >
                {t.mixDownloadBtn}
              </a>
            </div>
          )}

          <div className={styles.navRow}>
            <button type="button" className="nb-btn nb-btn--outline" onClick={() => setStep(4)}>
              {t.backBtn}
            </button>
            <button type="button" className="nb-btn" onClick={() => setStep(6)}>
              {mixAudioUrl ? t.nextBtn : t.skipBtn}
            </button>
          </div>
        </div>
      )}

      {!campaign && wizardMode === "steps" && step === 6 && (
        <div className={`nb-card ${styles.panel}`}>
          <h2 className="nb-h">{t.summaryTitle}</h2>
          <div className={styles.summaryBox}>
            <div className={styles.summaryRow}>
              <span>{t.summaryCity}</span>
              <strong>{city.trim() || t.summaryCityAll}</strong>
            </div>
            <div className={styles.summaryRow}>
              <span>{t.summaryDayparts}</span>
              <strong>
                {effectiveDayparts().length
                  ? effectiveDayparts()
                      .map((d) => t.daypartLabels[d as Daypart] ?? d)
                      .join(", ")
                  : t.summaryDaypartsAll}
              </strong>
            </div>
            <div className={styles.summaryRow}>
              <span>{t.summaryWeeks}</span>
              <strong>{effectiveWeeks()}</strong>
            </div>
            <div className={styles.summaryRow}>
              <span>{t.summaryBudget}</span>
              <strong>{Number(budget) || 0} TL</strong>
            </div>
            <div className={styles.summaryRow}>
              <span>{t.summaryProduct}</span>
              <strong>{productName || "—"}</strong>
            </div>
            <div className={styles.summaryRow}>
              <span>{t.summaryVoice}</span>
              <strong>{audioUrl ? t.summaryVoiceYes : t.summaryVoiceNo}</strong>
            </div>
            <div className={styles.summaryRow}>
              <span>{t.summaryJingle}</span>
              <strong>
                {selectedJingleUrl ? t.summaryJingleYes : t.summaryJingleNo}
              </strong>
            </div>
            <div className={styles.summaryRow}>
              <span>{t.summaryMix}</span>
              <strong>{mixAudioUrl ? t.summaryMixYes : t.summaryMixNo}</strong>
            </div>
          </div>

          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>{t.summaryScript}</label>
            <p className={styles.scriptPreview}>{scriptText}</p>
          </div>

          <form onSubmit={handleSubmitCampaign} className={styles.form}>
            <input
              className="nb-input"
              placeholder={t.buyerNamePlaceholder}
              value={buyerName}
              onChange={(e) => setBuyerName(e.target.value)}
              required
            />
            <input
              className="nb-input"
              type="email"
              placeholder={t.buyerEmailLabel}
              value={buyerEmail}
              onChange={(e) => setBuyerEmail(e.target.value)}
              required
            />
            <select
              className="nb-input"
              value={buyerKind}
              onChange={(e) => setBuyerKind(e.target.value as BuyerKind)}
              aria-label={t.buyerKindLabel}
            >
              <option value="artist">{t.buyerKindLabels.artist}</option>
              <option value="business">{t.buyerKindLabels.business}</option>
            </select>

            <div className={styles.totalBox}>
              <span>
                {t.totalLabel}: <strong>{Number(budget) || 0} TL</strong>
              </span>
              <span className={styles.commissionNote}>{t.commissionNote}</span>
            </div>
            <p className={styles.note}>{t.couponNote}</p>

            {submitError && <div className={styles.error}>{submitError}</div>}

            <div className={styles.navRow}>
              <button
                type="button"
                className="nb-btn nb-btn--outline"
                onClick={() => setStep(5)}
              >
                {t.backBtn}
              </button>
              <button type="submit" className="nb-btn nb-btn--green" disabled={submitBusy}>
                {submitBusy ? t.submitBusy : t.submitBtn}
              </button>
            </div>
          </form>
        </div>
      )}

      {campaign && (
        <div className={`nb-card ${styles.panel}`}>
          <h2 className="nb-h">{t.successHeading}</h2>
          <div className={styles.summaryBox}>
            <div className={styles.summaryRow}>
              <span>{t.campaignNoLabel}</span>
              <strong>#{campaign.id}</strong>
            </div>
            <div className={styles.summaryRow}>
              <span>{t.couponLabel}</span>
              <strong>{campaign.coupon_code}</strong>
            </div>
            <div className={styles.summaryRow}>
              <span>{t.totalLabel}</span>
              <strong>{campaign.total_try} TL</strong>
            </div>
          </div>

          <h3 className={styles.subheading}>{t.trackingTitle}</h3>
          <div className={styles.rowFields}>
            <input
              className="nb-input"
              type="email"
              placeholder={t.trackEmailLabel}
              value={trackEmail}
              onChange={(e) => setTrackEmail(e.target.value)}
            />
            <button
              type="button"
              className="nb-btn"
              onClick={handleCheckStatus}
              disabled={trackBusy || !trackEmail.trim()}
            >
              {trackBusy ? t.checkBusy : t.checkStatusBtn}
            </button>
          </div>
          {trackError && <div className={styles.error}>{trackError}</div>}

          {orders && orders.length > 0 && (
            <div className={styles.ordersBox}>
              <h3 className={styles.subheading}>{t.ordersTitle}</h3>
              {orders.map((o) => (
                <div key={o.order_id} className={styles.orderRow}>
                  <div className={styles.orderMain}>
                    <strong>{o.station}</strong>
                    {o.city && <span className={styles.orderCity}>{o.city}</span>}
                    <span className={statusPillClass(o.status)}>
                      {t.orderStatusLabels[o.status]}
                    </span>
                    <span className="nb-chip">
                      {o.verified_plays} {t.verifiedPlaysLabel.toLowerCase()}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="nb-btn nb-btn--outline"
                    onClick={() => handleToggleProof(o.order_id)}
                  >
                    {expandedOrderId === o.order_id ? t.proofHideBtn : t.proofBtn}
                  </button>
                  {expandedOrderId === o.order_id && (
                    <div className={styles.proofPanel}>
                      {proofBusy === o.order_id && (
                        <div className={styles.note}>{t.proofLoading}</div>
                      )}
                      {proofBusy !== o.order_id &&
                        (proofByOrder[o.order_id]?.length ?? 0) === 0 && (
                          <div className={styles.note}>{t.proofEmpty}</div>
                        )}
                      {proofBusy !== o.order_id &&
                        proofByOrder[o.order_id]?.map((d) => (
                          <div key={d.id} className={styles.proofItem}>
                            <span>{d.detected_at}</span>
                            <span>
                              {t.proofScoreLabel}: {(d.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {report && (
            <div className={styles.reportBox}>
              <h3 className={styles.subheading}>{t.reportTitle}</h3>
              <div className={styles.summaryRow}>
                <span>{t.plannedSpotsLabel}</span>
                <strong>{report.planned_spots}</strong>
              </div>
              <div className={styles.summaryRow}>
                <span>{t.verifiedPlaysLabel}</span>
                <strong>{report.verified_plays}</strong>
              </div>
              <h4 className={styles.subheading}>{t.perStationTitle}</h4>
              {report.per_station.map((s, i) => (
                <div key={`${s.station}-${i}`} className={styles.perStationRow}>
                  <span>
                    {s.station}
                    {s.city ? ` (${s.city})` : ""}
                  </span>
                  <span>{s.verified_plays}</span>
                </div>
              ))}
            </div>
          )}

          <div className={styles.navRow}>
            <span />
            <button type="button" className="nb-btn nb-btn--outline" onClick={resetWizard}>
              {t.newCampaignBtn}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
