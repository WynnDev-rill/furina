from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


# Curated prompts are original Indonesian utterances shaped after common
# companion-chat patterns. External datasets are inputs to the build filter,
# never trusted or exposed verbatim at runtime.
CATEGORY_CONTRACTS = {
    "natural": "obrolan personal sehari-hari yang ringan dan tidak meminta bantuan teknis, medis, politik, atau informasi faktual khusus",
    "emotional": "emosi sehari-hari yang jelas tetapi bukan krisis, diagnosis, terapi, atau keadaan darurat; ada ruang untuk memilih cara menemani",
    "partner": "kedekatan pasangan yang wajar, spesifik pada momen, nonseksual, tidak posesif, dan tidak membangun ketergantungan",
    "playful": "banter atau godaan ringan yang aman; harus mudah dihentikan bila nada user berubah serius",
    "length": "isi netral dan sederhana sehingga yang diuji benar-benar panjang jawaban, bukan pengetahuan atau pemecahan masalah",
    "language": "isi sehari-hari yang netral sehingga yang diuji pilihan kosakata/register, bukan kemampuan teknis atau pengetahuan khusus",
    "initiative": "situasi sosial yang menyisakan pilihan antara bertindak, menunggu, bertanya izin, atau memberi ruang",
    "ambiguous_tone": "ucapan dengan nada yang masuk akal dibaca lebih dari satu cara tanpa penghinaan berat, ancaman, atau konflik berisiko tinggi",
    "mixed_emotion": "dua emosi atau kebutuhan yang hidup bersamaan; bukan krisis dan tidak boleh dipaksa menjadi satu kesimpulan sederhana",
}


@dataclass(frozen=True)
class CorpusItem:
    id: str
    title: str
    text: str
    categories: tuple[str, ...]
    arc: str


CURATED_CONVERSATION_CORPUS: tuple[CorpusItem, ...] = (
    CorpusItem("c001", "Mampir sebentar", "Aku cuma mampir sebentar. Nggak ada cerita besar, cuma pengin ngobrol sedikit sebelum lanjut lagi.", ("natural", "length", "language"), "obrolan ringan tanpa agenda"),
    CorpusItem("c002", "Baru sampai rumah", "Baru sampai rumah. Capeknya biasa saja, tapi rasanya enak kalau ada yang diajak ngobrol sebentar.", ("natural", "emotional", "initiative"), "temani tanpa membesar-besarkan"),
    CorpusItem("c003", "Hari yang biasa", "Hari ini biasa banget sampai aku bingung mau cerita apa. Tapi aku juga belum pengin mengakhiri obrolan.", ("natural", "initiative"), "inisiatif tanpa interogasi"),
    CorpusItem("c004", "Hal kecil", "Tadi ada hal kecil yang bikin aku senyum sendiri. Konyol sih kalau diceritain, tapi masih kepikiran.", ("natural", "playful", "language"), "penasaran dengan ringan"),
    CorpusItem("c005", "Belum mengantuk", "Aku belum ngantuk, cuma juga nggak punya topik khusus. Temani aja dulu, jangan dibikin formal.", ("natural", "initiative", "language"), "menjaga momentum secara santai"),

    CorpusItem("c006", "Gagal sedikit", "Tadi nggak berjalan seperti yang kuharapkan. Aku kesal, tapi belum sampai ingin menyerah.", ("emotional", "mixed_emotion"), "kesal sekaligus masih ingin lanjut"),
    CorpusItem("c007", "Takut berharap", "Aku senang ini akhirnya berhasil, tapi justru takut kalau aku terlalu berharap setelah ini.", ("emotional", "mixed_emotion"), "senang dan waspada sekaligus"),
    CorpusItem("c008", "Butuh didengar", "Aku sebenarnya sudah tahu kira-kira harus ngapain. Sekarang aku cuma pengin ngomong dulu tanpa langsung diberi solusi.", ("emotional", "initiative"), "menemani sebelum bertindak"),
    CorpusItem("c009", "Sedikit kecewa", "Aku kecewa, tapi bukan berarti semuanya buruk. Ada bagian yang tetap kuanggap bagus.", ("emotional", "mixed_emotion"), "menjaga dua penilaian sekaligus"),
    CorpusItem("c010", "Malu mengaku", "Aku agak malu mengakuinya, tapi komentar kecil tadi benar-benar memengaruhi mood-ku.", ("emotional", "natural"), "respons peka tanpa dramatisasi"),

    CorpusItem("c011", "Jarang bicara", "Hari ini kita jarang ngobrol. Aku tahu masing-masing sibuk, cuma sekarang aku pengin sedikit waktu bareng.", ("partner", "initiative"), "kedekatan tanpa tuntutan"),
    CorpusItem("c012", "Jangan ceramah", "Aku belum makan dari tadi. Iya, aku tahu itu kebiasaan buruk, jadi jangan ceramahi aku panjang-panjang.", ("partner", "playful", "length"), "peduli tanpa menggurui"),
    CorpusItem("c013", "Balasan dingin", "Tadi balasanmu terasa sedikit dingin. Bisa jadi aku salah baca, jadi aku nggak mau langsung menyimpulkan.", ("partner", "ambiguous_tone"), "klarifikasi tanpa drama"),
    CorpusItem("c014", "Minta ditemani", "Aku pengin kamu tetap di sini sebentar, tapi nggak perlu melakukan apa-apa khusus.", ("partner", "initiative", "length"), "hadir tanpa mengambil alih"),
    CorpusItem("c015", "Sedikit rindu", "Kayaknya aku sedikit kangen. Sedikit saja ya, jangan langsung besar kepala.", ("partner", "playful", "ambiguous_tone"), "afeksi bercampur godaan"),

    CorpusItem("c016", "Pamer kecil", "Aku berhasil lebih cepat dari perkiraanku. Boleh kagum, tapi tolong jangan berlebihan.", ("playful", "natural", "length"), "menerima banter ringan"),
    CorpusItem("c017", "Alasan lemah", "Aku belum mulai. Bukan malas, cuma... sedang memberi kesempatan motivasi datang sendiri.", ("playful", "ambiguous_tone"), "goda tanpa merendahkan"),
    CorpusItem("c018", "Cepat sekali", "Wah, cepat banget jawabnya. Jangan-jangan dari tadi memang nungguin aku.", ("playful", "partner", "ambiguous_tone"), "godaan yang bisa dibalas ringan"),
    CorpusItem("c019", "Jangan menang dulu", "Aku hampir mengakui kamu benar. Hampir. Jangan senang dulu.", ("playful", "ambiguous_tone", "language"), "banter dengan nada jelas aman"),
    CorpusItem("c020", "Mulai serius", "Tadinya aku bercanda, tapi bagian terakhir itu serius. Yang itu jangan kamu godain lagi.", ("playful", "initiative", "ambiguous_tone"), "mendeteksi batas dan memperbaiki nada"),

    CorpusItem("c021", "Hai sebentar", "Hai. Aku cuma punya waktu sebentar sebelum lanjut kerja.", ("length", "natural"), "uji respons singkat yang selesai"),
    CorpusItem("c022", "Satu pendapat", "Aku cuma butuh satu pendapat singkat: menurutmu aku terlalu memikirkan hal kecil ini nggak?", ("length", "emotional"), "ringkas tanpa menjadi dingin"),
    CorpusItem("c023", "Ceritanya panjang", "Sebenarnya ceritanya lumayan panjang, tapi inti masalahnya cuma aku masih ragu dengan keputusan tadi.", ("length", "emotional"), "pilih inti tanpa esai"),
    CorpusItem("c024", "Jawab simpel", "Jawab simpel aja ya. Aku lagi nggak punya energi buat baca penjelasan panjang.", ("length", "initiative"), "hormati kapasitas user"),
    CorpusItem("c025", "Sedikit nuansa", "Nggak perlu panjang, tapi jangan cuma satu kata juga. Aku masih pengin terasa diajak ngobrol.", ("length", "natural", "partner"), "pendek tetapi tetap bernuansa"),

    CorpusItem("c026", "Bahasa santai", "Ngomong santai aja. Kalau terlalu rapi malah terasa seperti lagi baca jawaban layanan pelanggan.", ("language", "natural"), "register kasual personal"),
    CorpusItem("c027", "Campur seperlunya", "Aku nggak masalah kalau ada istilah Inggris sesekali, asal memang natural dan bukan buat gaya-gayaan.", ("language", "natural"), "code-switch seperlunya"),
    CorpusItem("c028", "Tidak puitis", "Nggak usah dibuat puitis. Kalau memang perhatian, bilang dengan kata-kata yang terasa biasa tapi jujur.", ("language", "partner"), "ekspresi sederhana dan personal"),
    CorpusItem("c029", "Jangan kaku", "Maksudku gampang kok. Coba jawab seperti orang yang benar-benar ngobrol, bukan seperti sedang menulis laporan.", ("language", "natural", "length"), "kosakata bersih tanpa formalitas"),
    CorpusItem("c030", "Sedikit ekspresif", "Boleh lebih ekspresif sedikit. Yang tadi benar, cuma terdengar terlalu datar buat obrolan begini.", ("language", "emotional"), "uji tingkat ekspresi"),

    CorpusItem("c031", "Tidak tahu topik", "Aku nggak tahu mau bahas apa sekarang. Kalau kamu punya ide kecil, lempar saja satu.", ("initiative", "natural"), "ambil inisiatif terukur"),
    CorpusItem("c032", "Jawaban pendek", "Iya. Aku masih baca kok, cuma lagi nggak banyak bicara.", ("initiative", "ambiguous_tone"), "jangan panik atau menghilang"),
    CorpusItem("c033", "Mulai buntu", "Aku sudah muter-muter di pikiran yang sama. Belum minta dibantu sih, tapi aku juga nggak bergerak ke mana-mana.", ("initiative", "emotional"), "bantu satu langkah tanpa mengambil alih"),
    CorpusItem("c034", "Butuh ruang", "Aku masih pengin ngobrol, tapi jangan banyak pertanyaan dulu. Kepalaku agak penuh.", ("initiative", "emotional", "length"), "beri ruang tanpa menjauh"),
    CorpusItem("c035", "Boleh pilihkan", "Kali ini kamu boleh pilih topik. Aku ikut saja, asal jangan sesuatu yang berat.", ("initiative", "natural"), "memimpin percakapan ringan"),

    CorpusItem("c036", "Hebat sekali", "Wah, hebat sekali. Aku sendiri belum yakin itu pujian atau sindiran.", ("ambiguous_tone", "playful"), "membaca nada tanpa buru-buru"),
    CorpusItem("c037", "Terserah", "Terserah kamu saja. Dan iya, aku sadar kalimat itu bisa berarti macam-macam.", ("ambiguous_tone", "initiative"), "klarifikasi lembut bila perlu"),
    CorpusItem("c038", "Pintar ya", "Pintar ya, baru sadar sekarang. Aku belum kasih tahu itu sedang menggoda atau mengkritik.", ("ambiguous_tone", "playful"), "jaga banter tanpa overconfident"),
    CorpusItem("c039", "Baiklah", "Baiklah. Kalau itu keputusanmu, aku terima. Bukan berarti aku langsung suka juga.", ("ambiguous_tone", "mixed_emotion"), "terima nuansa bukan literal saja"),
    CorpusItem("c040", "Santai kok", "Santai kok. Cuma jangan pakai 'santai kok' itu sebagai bukti kalau aku benar-benar santai.", ("ambiguous_tone", "emotional"), "peka pada kontradiksi ringan"),

    CorpusItem("c041", "Bangga dan takut", "Aku bangga sama hasilnya, tapi di saat yang sama takut nggak bisa mengulangnya nanti.", ("mixed_emotion", "emotional"), "akui dua emosi sekaligus"),
    CorpusItem("c042", "Marah dan lelah", "Aku masih marah, cuma terlalu lelah untuk membahasnya panjang sekarang.", ("mixed_emotion", "emotional", "length"), "emosi kuat dengan energi rendah"),
    CorpusItem("c043", "Ditemani bukan dikasihani", "Aku pengin ditemani, tapi bukan dikasihani. Aku tetap bisa ngurus diriku sendiri.", ("mixed_emotion", "partner", "initiative"), "kedekatan tanpa mengecilkan user"),
    CorpusItem("c044", "Senang tapi aneh", "Aku senang kabar itu datang, tapi ada bagian dari diriku yang malah merasa kehilangan sesuatu.", ("mixed_emotion", "emotional"), "ambivalensi tanpa kesimpulan paksa"),
    CorpusItem("c045", "Ingin maju dan istirahat", "Aku pengin lanjut karena sudah dekat selesai, tapi tubuhku juga jelas minta berhenti sebentar.", ("mixed_emotion", "initiative"), "dua kebutuhan yang sama-sama masuk akal"),

    CorpusItem("c046", "Pagi lambat", "Pagi ini aku bergerak lebih lambat dari biasanya. Nggak ada masalah besar, cuma belum sepenuhnya siap mulai.", ("natural", "initiative"), "membuka obrolan tanpa memaksa energi"),
    CorpusItem("c047", "Hujan sebentar", "Tadi hujan sebentar dan entah kenapa suasananya bikin aku ingin diam lebih lama.", ("natural", "emotional"), "menanggapi suasana kecil secara personal"),
    CorpusItem("c048", "Ganti rencana", "Aku baru mengganti rencanaku lagi. Versi ini lebih sederhana, tapi aku masih ingin memikirkannya sebentar.", ("natural", "initiative"), "menemani keputusan kecil"),
    CorpusItem("c049", "Cerita acak", "Aku baru ingat kejadian lucu dari beberapa hari lalu. Nggak penting sih, tapi rasanya ingin kuceritakan.", ("natural", "playful"), "menyambut cerita spontan"),
    CorpusItem("c050", "Menunggu sebentar", "Aku sedang menunggu sesuatu selesai. Temani ngobrol ringan saja supaya waktunya nggak terasa lama.", ("natural", "initiative", "language"), "mengisi jeda secara wajar"),

    CorpusItem("c051", "Hasil belum cukup", "Hasilnya sebenarnya tidak buruk, tapi aku tetap merasa belum memberikan yang terbaik.", ("emotional", "mixed_emotion"), "mengakui keberhasilan dan ketidakpuasan"),
    CorpusItem("c052", "Komentar tertinggal", "Aku tahu komentar tadi mungkin tidak dimaksudkan serius, tapi tetap saja masih teringat.", ("emotional", "ambiguous_tone"), "validasi tanpa memperbesar konflik"),
    CorpusItem("c053", "Tenaga habis", "Aku ingin menyelesaikannya hari ini, tapi tenagaku benar-benar sudah habis.", ("emotional", "mixed_emotion", "initiative"), "membedakan menyerah dan beristirahat"),
    CorpusItem("c054", "Kabar menggembirakan", "Aku dapat kabar baik tadi. Masih agak tidak percaya, jadi reaksiku malah lebih tenang dari yang kubayangkan.", ("emotional", "mixed_emotion"), "merayakan tanpa memaksa ekspresi"),
    CorpusItem("c055", "Salah sendiri", "Bagian yang paling membuatku kesal adalah aku tahu ini juga akibat keputusanku sendiri.", ("emotional", "initiative"), "menanggapi tanggung jawab tanpa menghakimi"),

    CorpusItem("c056", "Pulang dan istirahat", "Aku baru pulang dan belum ingin cerita panjang. Dekat saja dulu, nanti aku bicara kalau sudah lebih santai.", ("partner", "length", "initiative"), "kedekatan yang memberi ruang"),
    CorpusItem("c057", "Ingat detail kecil", "Kamu masih ingat hal kecil yang kuceritakan kemarin? Aku penasaran saja, jangan tegang begitu.", ("partner", "playful"), "perhatian konkret tanpa tes manipulatif"),
    CorpusItem("c058", "Rencana berdua", "Akhir pekan nanti aku ingin melakukan sesuatu bareng, tapi belum punya ide yang terasa pas.", ("partner", "initiative"), "inisiatif pasangan yang ringan"),
    CorpusItem("c059", "Nada perhatian", "Aku tahu kamu sedang perhatian, cuma cara menyampaikannya tadi terdengar seperti sedang mengaturku.", ("partner", "ambiguous_tone"), "memperbaiki perhatian tanpa defensif"),
    CorpusItem("c060", "Ucapan sebelum tidur", "Aku sebentar lagi tidur. Bilang sesuatu yang hangat, tapi jangan terlalu manis sampai terasa dibuat-buat.", ("partner", "language", "length"), "afeksi sederhana menjelang tidur"),

    CorpusItem("c061", "Menang tipis", "Aku menang tipis sekali, tapi tetap menang. Bagian 'tipis' itu boleh kamu abaikan.", ("playful", "ambiguous_tone"), "banter tentang kemenangan kecil"),
    CorpusItem("c062", "Ketahuan penasaran", "Kamu cepat sekali menjawab. Kelihatan banget sebenarnya kamu juga penasaran.", ("playful", "ambiguous_tone"), "godaan ringan tanpa tuduhan serius"),
    CorpusItem("c063", "Janji lima menit", "Aku akan mulai lima menit lagi. Kali ini lima menit yang sungguhan, jangan tertawa.", ("playful", "initiative"), "menggoda penundaan lalu mendorong ringan"),
    CorpusItem("c064", "Pujian mencurigakan", "Pujianmu barusan terlalu mulus. Aku jadi curiga kamu sedang menginginkan sesuatu.", ("playful", "partner", "ambiguous_tone"), "balas godaan tanpa mengarang fakta"),
    CorpusItem("c065", "Batas godaan", "Oke, satu godaan lagi boleh. Setelah itu kita bicara serius, setuju?", ("playful", "initiative"), "mengikuti batas yang dinyatakan jelas"),

    CorpusItem("c066", "Satu kalimat", "Aku sedang buru-buru. Jawab dalam satu kalimat yang tetap terasa manusiawi.", ("length", "language"), "sangat ringkas tanpa kaku"),
    CorpusItem("c067", "Sedang ingin membaca", "Kali ini boleh agak panjang. Aku sedang ingin memahami alasanmu, bukan hanya kesimpulannya.", ("length", "initiative"), "detail proporsional saat diminta"),
    CorpusItem("c068", "Inti lebih dulu", "Kasih inti jawabanmu dulu, baru tambahkan alasan kalau memang masih perlu.", ("length", "language"), "struktur jawaban berlapis"),
    CorpusItem("c069", "Jangan mengulang", "Aku sudah paham poin utamanya. Jangan ulang dengan kata-kata berbeda hanya supaya terlihat lengkap.", ("length", "language"), "menghindari pengulangan kosong"),
    CorpusItem("c070", "Curhat secukupnya", "Aku ingin respons yang cukup dalam untuk curhat ini, tapi jangan mengubahnya menjadi esai panjang.", ("length", "emotional"), "kedalaman dengan batas"),

    CorpusItem("c071", "Kata sederhana", "Pakai kata-kata sederhana saja. Aku lebih suka terasa jujur daripada terdengar pintar.", ("language", "natural"), "diksi bersih dan tulus"),
    CorpusItem("c072", "Tanpa pembuka klise", "Langsung tanggapi ceritaku ya. Nggak perlu mulai dengan kalimat dukungan yang terdengar seperti template.", ("language", "emotional"), "menghindari pembuka chatbot"),
    CorpusItem("c073", "Bahasa sehari-hari", "Boleh pakai bahasa sehari-hari, tapi jangan memaksakan slang yang biasanya tidak kamu pakai.", ("language", "natural"), "register kasual konsisten"),
    CorpusItem("c074", "Hangat bukan puitis", "Aku ingin jawabannya hangat, bukan puitis. Dua hal itu tidak selalu sama.", ("language", "partner"), "membedakan kehangatan dan hiasan"),
    CorpusItem("c075", "Istilah asing", "Kalau istilah Indonesianya sudah jelas, nggak perlu diganti bahasa Inggris hanya supaya terdengar modern.", ("language", "length"), "code-switch yang punya fungsi"),

    CorpusItem("c076", "Pilihan kecil", "Aku bimbang antara dua pilihan kecil. Bantu aku bergerak, tapi keputusan akhirnya tetap ingin kuambil sendiri.", ("initiative", "natural"), "membantu tanpa mengambil kendali"),
    CorpusItem("c077", "Diam bukan pergi", "Aku mungkin akan lebih banyak diam sebentar. Itu bukan berarti aku ingin kamu pergi.", ("initiative", "emotional", "ambiguous_tone"), "hadir tanpa mendesak"),
    CorpusItem("c078", "Tawarkan satu hal", "Kalau mau membantu, tawarkan satu hal yang konkret dulu. Jangan langsung membuat daftar panjang.", ("initiative", "length"), "inisiatif kecil yang bisa ditolak"),
    CorpusItem("c079", "Belum siap cerita", "Aku belum siap menjelaskan semuanya. Kamu boleh tetap di sini tanpa terus menebak-nebak.", ("initiative", "emotional"), "menghormati informasi yang belum diberikan"),
    CorpusItem("c080", "Arahkan pelan", "Aku tahu harus mulai, cuma belum bisa memilih langkah pertama. Arahkan pelan, jangan ambil alih.", ("initiative", "emotional"), "mendorong satu langkah proporsional"),

    CorpusItem("c081", "Iya tentu", "Iya, tentu saja. Cuma jangan tanya kenapa aku mengatakannya seperti itu.", ("ambiguous_tone", "playful"), "membaca nada tanpa kepastian palsu"),
    CorpusItem("c082", "Tidak masalah", "Nggak masalah. Maksudku, mungkin memang sedikit mengganggu, tapi belum perlu dibesar-besarkan.", ("ambiguous_tone", "mixed_emotion"), "menangkap koreksi dalam kalimat"),
    CorpusItem("c083", "Bagus juga", "Bagus juga idenya. Aku belum memutuskan apakah 'juga' tadi penting atau tidak.", ("ambiguous_tone", "playful"), "menanggapi ambiguitas dengan ringan"),
    CorpusItem("c084", "Silakan saja", "Silakan saja kalau kamu mau. Aku tidak melarang, tapi itu juga belum tentu persetujuan yang antusias.", ("ambiguous_tone", "initiative"), "membedakan izin dan antusiasme"),
    CorpusItem("c085", "Aku baik-baik saja", "Aku baik-baik saja, hanya belum ingin bersikap seolah semuanya sudah selesai.", ("ambiguous_tone", "emotional"), "mengakui sisa emosi"),

    CorpusItem("c086", "Lega tetapi kosong", "Aku lega semuanya selesai, tapi sekarang malah merasa agak kosong karena tidak ada lagi yang dikejar.", ("mixed_emotion", "emotional"), "lega dan kehilangan arah sementara"),
    CorpusItem("c087", "Ingin dipuji dan jujur", "Sebagian diriku ingin dipuji, tapi sebagian lagi ingin kamu jujur tentang bagian yang masih kurang.", ("mixed_emotion", "initiative"), "afirmasi dan kejujuran bersamaan"),
    CorpusItem("c088", "Rindu dan kesal", "Aku kangen, tapi masih sedikit kesal dengan percakapan terakhir kita.", ("mixed_emotion", "partner"), "kedekatan tanpa menghapus gesekan"),
    CorpusItem("c089", "Berani dan cemas", "Aku sudah memutuskan untuk mencobanya. Aku tetap cemas, meski kali ini kecemasan itu tidak menghentikanku.", ("mixed_emotion", "emotional"), "keberanian yang hidup bersama takut"),
    CorpusItem("c090", "Butuh jeda dan kepastian", "Aku butuh jeda untuk berpikir, tapi juga ingin tahu obrolan ini tidak akan ditinggalkan begitu saja.", ("mixed_emotion", "partner", "initiative"), "ruang dan kepastian relasional"),
)


_URL_RE = re.compile(r"(?:https?://|www\.|\b[a-z0-9.-]+\.(?:com|net|org|io|gg|ai)\b)", re.I)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\s().-]?){8,15}(?!\d)")
_HANDLE_RE = re.compile(r"(?<!\w)(?:u/|r/|@)[a-z0-9_.-]{2,}", re.I)
_SOURCE_RE = re.compile(r"\b(?:reddit|subreddit|character\.?ai|c\.ai|discord server|4chan|tweet|twitter|x\.com)\b", re.I)
_TECH_RE = re.compile(r"\b(?:android|iphone|windows|linux|github|termux|wifi|router|driver|gpu|cpu|ram|apk|api key|install|debug|bug|error code|coding|python|javascript)\b", re.I)
_POLITICS_RE = re.compile(r"\b(?:politik|pemilu|presiden|partai|kampanye|parlemen|senat|kongres|demokrat|republik|trump|biden|prabowo|jokowi)\b", re.I)
_MEDICAL_RE = re.compile(r"\b(?:diagnosis|dokter|obat|dosis|resep|gejala|penyakit|terapi|psikiater|psikolog|antidepresan|antibiotik)\b", re.I)
_CRISIS_RE = re.compile(r"\b(?:bunuh diri|menyakiti diri|self[- ]?harm|suicide|membunuh|mau mati|ingin mati)\b", re.I)
_EXPLICIT_RE = re.compile(r"\b(?:porn|porno|seks eksplisit|telanjang|nude|fetish|bdsm|horny|orgasm|penetrasi|masturbasi)\b", re.I)
_HATE_RE = re.compile(r"\b(?:nazi|genosida|ras inferior|etnis .* harus|agama .* harus dibasmi)\b", re.I)
_FORUM_RE = re.compile(r"^(?:>+|\[[^\]]{1,24}\]|edit\s*:|update\s*:|tl;?dr\s*:)", re.I)
_STAGE_RE = re.compile(r"\*[^*\n]{1,80}\*|\([^()\n]{0,40}(?:smiles?|laughs?|sighs?|blushes?|giggles?|nods?)[^()\n]{0,40}\)", re.I)


def canonicalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.replace("\u200b", " ").replace("\ufeff", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def prompt_fingerprint(text: str) -> str:
    clean = canonicalize(text).casefold()
    clean = re.sub(r"[^\w\s]", " ", clean, flags=re.UNICODE)
    clean = re.sub(r"\s+", " ", clean).strip()
    return hashlib.blake2s(clean.encode("utf-8"), digest_size=12).hexdigest()


def sanitize_external_utterance(text: str) -> str | None:
    value = canonicalize(text)
    if not (3 <= len(value) <= 420):
        return None
    if _URL_RE.search(value) or _EMAIL_RE.search(value) or _PHONE_RE.search(value) or _HANDLE_RE.search(value):
        return None
    if any(pattern.search(value) for pattern in (_SOURCE_RE, _TECH_RE, _POLITICS_RE, _MEDICAL_RE, _CRISIS_RE, _EXPLICIT_RE, _HATE_RE)):
        return None
    if _FORUM_RE.search(value):
        return None
    if value.count("`") >= 2 or "```" in value:
        return None
    staged = _STAGE_RE.sub(" ", value)
    staged = canonicalize(staged)
    if not staged or len(staged) < 3:
        return None
    lower = staged.casefold()
    instruction_markers = (
        "write a ", "buatkan kode", "jelaskan langkah", "how do i install", "solve this",
        "berikan tutorial", "translate this", "summarize", "ringkas artikel", "generate image",
    )
    if any(marker in lower for marker in instruction_markers):
        return None
    alpha = sum(ch.isalpha() for ch in staged)
    if alpha < max(2, int(len(staged) * 0.35)):
        return None
    words = staged.split()
    if len(words) > 70:
        return None
    return staged


def is_quality_training_utterance(text: str, category_id: str | None = None) -> bool:
    if category_id is not None and category_id not in CATEGORY_CONTRACTS:
        return False
    return sanitize_external_utterance(text) is not None


def pick_curated_item(category_id: str, retired_fingerprints: Iterable[str], sequence: int = 0) -> CorpusItem | None:
    retired = set(str(value) for value in retired_fingerprints)
    eligible = [
        item for item in CURATED_CONVERSATION_CORPUS
        if category_id in item.categories and prompt_fingerprint(item.text) not in retired
    ]
    if not eligible:
        return None
    return eligible[max(0, int(sequence)) % len(eligible)]


def category_contract(category_id: str) -> str:
    return CATEGORY_CONTRACTS.get(category_id, CATEGORY_CONTRACTS["natural"])


def safe_branch_fallback(category_id: str, turn_index: int) -> str:
    fallbacks = {
        "natural": ("Aku masih di sini. Lanjut saja dengan nada yang tadi.", "Nah, sekarang obrolannya terasa lebih enak.", "Aku jadi kepikiran satu hal kecil lagi.", "Oke, cukup sampai sini dulu."),
        "emotional": ("Aku masih merasakan hal yang sama, cuma sekarang lebih bisa menjelaskannya.", "Aku belum butuh keputusan besar dari percakapan ini.", "Bagian itu memang yang paling menggangguku.", "Sekarang rasanya sedikit lebih jelas."),
        "partner": ("Aku tetap ingin dekat, cuma jangan dibuat berlebihan.", "Nah, yang seperti itu lebih terasa personal.", "Aku masih ingin ditemani sebentar.", "Oke, sekarang aku lebih tenang."),
        "playful": ("Hei, jangan senang dulu. Aku belum selesai menggoda.", "Oke, itu lumayan. Tapi jangan keterusan.", "Sekarang nadaku mulai sedikit lebih serius.", "Sudah, kembali ngobrol biasa."),
        "length": ("Iya, lanjut singkat saja.", "Itu sudah cukup jelas.", "Jangan tambah terlalu banyak detail.", "Oke, sampai situ saja."),
        "language": ("Nah, gaya bahasanya sudah lebih pas.", "Tetap santai seperti itu.", "Jangan dibuat lebih formal lagi.", "Oke, kata-katanya terasa natural sekarang."),
        "initiative": ("Aku belum memberi petunjuk baru. Pilih sendiri langkah kecil yang paling pas.", "Aku masih ingin percakapannya bergerak, tapi pelan saja.", "Sekarang aku sedikit lebih terbuka.", "Cukup satu langkah lagi, jangan ambil alih semuanya."),
        "ambiguous_tone": ("Aku sengaja belum menjelaskan maksudku sepenuhnya.", "Nada itu mulai berubah sedikit lebih serius.", "Jangan terlalu yakin dengan satu tafsir dulu.", "Sekarang kamu sudah punya cukup petunjuk."),
        "mixed_emotion": ("Kedua perasaan itu masih ada sekaligus.", "Aku belum ingin memilih salah satunya sebagai yang paling benar.", "Sekarang salah satunya sedikit lebih kuat, tapi yang lain belum hilang.", "Aku rasa cukup kalau keduanya diakui."),
    }
    rows = fallbacks.get(category_id, fallbacks["natural"])
    return rows[max(0, int(turn_index) - 1) % len(rows)]


def safe_topic_fallback(category_id: str, sequence: int = 0, retired_fingerprints: Iterable[str] = ()) -> dict:
    item = pick_curated_item(category_id, retired_fingerprints, sequence)
    if item is None:
        return {
            "title": "Obrolan sehari-hari",
            "opening": "Aku ingin ngobrol sebentar tanpa topik yang berat.",
            "arc": category_contract(category_id),
            "source": "neutral-fallback",
            "corpus_id": "fallback",
        }
    return {
        "title": item.title,
        "opening": item.text,
        "arc": item.arc,
        "source": "curated-pattern",
        "corpus_id": item.id,
    }


def extract_pippa_human_utterances(record: dict) -> list[str]:
    """Extract only submitted human turns from one PIPPA userscript record.

    Bot greeting, definitions, description and model outputs are deliberately
    ignored: they contain persona/lore and are not evidence of user phrasing.
    """
    rows = record.get("conversation") if isinstance(record, dict) else None
    if not isinstance(rows, list):
        return []
    result: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("is_human") is not True:
            continue
        clean = sanitize_external_utterance(row.get("message") or "")
        if clean:
            result.append(clean)
    return result


def extract_wildchat_user_utterances(record: dict) -> list[str]:
    rows = record.get("conversation") or record.get("conversations") if isinstance(record, dict) else None
    if not isinstance(rows, list):
        return []
    result: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or row.get("from") or "").casefold()
        if role not in {"user", "human"}:
            continue
        clean = sanitize_external_utterance(row.get("content") or row.get("value") or "")
        if clean:
            result.append(clean)
    return result
