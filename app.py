import os
import random
import uuid
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

import database
from config import SYSTEM_PROMPT_HIGH_ANTHRO, SYSTEM_PROMPT_LOW_ANTHRO, TASK_DESCRIPTION

# Ortam değişkenlerini ve veritabanını yükle
load_dotenv()
database.init_db()

# Sayfa yapılandırması
st.set_page_config(page_title="AI Etkileşim Araştırması", page_icon="🤖", layout="centered")

# Gemini API istemcisini başlat
api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("API Anahtarı bulunamadı! Lütfen .env dosyasını kontrol edin.")
    st.stop()

client = genai.Client(api_key=api_key)

# Session State (Oturum Değişkenleri) İlklendirme
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]
if "step" not in st.session_state:
    st.session_state.step = "consent"  # consent -> chat -> survey -> finished
if "condition" not in st.session_state:
    st.session_state.condition = random.choice(["Low_Anthro", "High_Anthro"])
if "messages" not in st.session_state:
    st.session_state.messages = []
if "turn_count" not in st.session_state:
    st.session_state.turn_count = 0
if "total_input_tokens" not in st.session_state:
    st.session_state.total_input_tokens = 0
if "total_output_tokens" not in st.session_state:
    st.session_state.total_output_tokens = 0
if "age" not in st.session_state:
    st.session_state.age = 20
if "ai_experience" not in st.session_state:
    st.session_state.ai_experience = "Haftada birkaç kez"


# ==========================================
# 1. ADIM: ONAM VE DEMOGRAFİK BİLGİLER
# ==========================================
if st.session_state.step == "consent":
    st.title("Akademik Araştırma Katılım Formu")
    st.write(
        """
        Bu çalışma, insan-yapay zeka etkileşimi üzerine yürütülen bilimsel bir araştırma projesidir.
        Deney yaklaşık **3-5 dakika** sürecektir. Katkılarınız için teşekkür ederiz.
        """
    )
    
    st.write("""3 dakikanızı alacak mini bir yapay zeka deneyine katılıp bana destek olur musunuz? 
             Testin sonunda yapay zekanın size özel bir şarkı hediyesi var 🎧"""
    )

    with st.form("demographics_form"):
        age = st.number_input("Yaşınız:", min_value=15, max_value=80, value=22)
        ai_exp = st.selectbox(
            "Yapay zeka araçlarını (ChatGPT, Gemini vb.) ne sıklıkla kullanıyorsunuz?",
            ["Hiç kullanmadım", "Ayda birkaç kez", "Haftada birkaç kez", "Hergün düzenli"],
        )
        agree = st.checkbox("Verilerimin anonim olarak akademik amaçla kullanılmasını onaylıyorum.")
        submit_btn = st.form_submit_button("Deneye Başla")

        if submit_btn:
            if not agree:
                st.warning("Lütfen onam kutucuğunu işaretleyin.")
            else:
                st.session_state.age = age
                st.session_state.ai_experience = ai_exp
                st.session_state.step = "chat"
                st.rerun()


# ==========================================
# 2. ADIM: CHAT VE GÖREV EKRANI
# ==========================================
elif st.session_state.step == "chat":
    # Arayüz başlığını koşula göre özelleştirme
    if st.session_state.condition == "High_Anthro":
        st.subheader("🤖 Asistan Nova ile Sohbet")
    else:
        st.subheader("⚙️ Sistem Metin Analiz Modülü")

    st.info(TASK_DESCRIPTION)

    # Sohbet geçmişini ekrana yaz
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Kullanıcıdan mesaj alma
    user_input = st.chat_input("Mesajınızı yazın...")

    if user_input:
        # Kullanıcı mesajını kaydet ve göster
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.turn_count += 1

        # Sistem promptunu koşula göre seç
        system_instruction = (
            SYSTEM_PROMPT_HIGH_ANTHRO
            if st.session_state.condition == "High_Anthro"
            else SYSTEM_PROMPT_LOW_ANTHRO
        )

        # Gemini API Çağrısı (Model: gemini-2.5-flash)
        with st.spinner("Yanıt oluşturuluyor..."):
            try:
                # API formatına uygun mesaj geçmişini hazırla
                contents = [
                    types.Content(
                        role="user" if m["role"] == "user" else "model",
                        parts=[types.Part.from_text(text=m["content"])],
                    )
                    for m in st.session_state.messages
                ]

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                    ),
                )

                bot_response = response.text
                st.session_state.messages.append({"role": "assistant", "content": bot_response})

                # Token sayılarını arka planda biriktir
                if response.usage_metadata:
                    st.session_state.total_input_tokens += (
                        response.usage_metadata.prompt_token_count or 0
                    )
                    st.session_state.total_output_tokens += (
                        response.usage_metadata.candidates_token_count or 0
                    )

            except Exception as e:
                st.error(f"Bir hata oluştu: {e}")

        st.rerun()

    # Görevi bitirme butonu
    if st.session_state.turn_count >= 2:
        st.write("---")
        if st.button("Görevi Tamamladım ve Ankete Geç ➡️", type="primary"):
            st.session_state.step = "survey"
            st.rerun()


# ==========================================
# 3. ADIM: MANİPÜLASYON KONTROLÜ VE ANKET
# ==========================================
elif st.session_state.step == "survey":
    st.title("Deneyim Değerlendirme Anketi")
    st.write(
        "Lütfen biraz önce etkileşimde bulunduğunuz yapay zeka sistemini aşağıdaki ifadelere göre değerlendirin."
    )
    st.caption("(1: Kesinlikle Katılmıyorum — 5: Kesinlikle Katılıyorum)")

    with st.form("survey_form"):
        st.markdown("**Algılanan İnsan Benzerliği (Anthropomorphism)**")
        anthro_1 = st.slider(
            "1. Sistem bana mekanik bir yazılımdan ziyade insan-benzeri bir his verdi.", 1, 5, 3
        )
        anthro_2 = st.slider("2. Bu yapay zekanın kendine özgü bir kişiliği olduğunu hissettim.", 1, 5, 3)

        st.markdown("**Sosyal Mevcudiyet (Social Presence)**")
        social_1 = st.slider(
            "3. Etkileşim sırasında karşımda gerçek bir sosyal muhatap varmış gibi hissettim.", 1, 5, 3
        )
        social_2 = st.slider("4. Sistemle kurduğum iletişim sıcak ve sosyaldi.", 1, 5, 3)

        st.markdown("**Görev Değerlendirmesi**")
        diff_1 = st.slider("5. Verilen görevi tamamlamak zihinsel olarak zorlayıcıydı.", 1, 5, 2)

        submit_survey = st.form_submit_button("Anketi Tamamla ve Gönder")

        if submit_survey:
            # Toplam token hesabı
            total_tokens = (
                st.session_state.total_input_tokens + st.session_state.total_output_tokens
            )

            # Verileri kaydet
            data_to_save = {
                "session_id": st.session_state.session_id,
                "condition": st.session_state.condition,
                "age": st.session_state.age,
                "ai_experience": st.session_state.ai_experience,
                "turn_count": st.session_state.turn_count,
                "total_input_tokens": st.session_state.total_input_tokens,
                "total_output_tokens": st.session_state.total_output_tokens,
                "total_tokens": total_tokens,
                "perceived_anthro_1": anthro_1,
                "perceived_anthro_2": anthro_2,
                "social_presence_1": social_1,
                "social_presence_2": social_2,
                "task_difficulty": diff_1,
            }

            database.save_experiment_data(data_to_save)
            st.session_state.step = "finished"
            st.rerun()


# ==========================================
# 4. ADIM: BİTİŞ EKRANI & SPOTIFY ŞARKI HEDİYESİ
# ==========================================
elif st.session_state.step == "finished":
    st.balloons()
    st.success("Tebrikler! Katılımınız başarıyla kaydedildi.")
    st.write("Araştırmamıza sağladığınız değerli katkılar için çok teşekkür ederiz.")
    
    st.write("---")
    st.subheader("🎵 Katkınız İçin Size Özel Nostaljik Türkçe Şarkı Hediyesi")

    # Nostaljik Türkçe Şarkı Havuzu
    # 50 Şarkılık Türkçe Nostalji ve Pop Havuzu
    SONG_LIST = [
        {"title": "Tarkan - Kuzu Kuzu", "note": "2000'lerin efsanevi zilli klasiği! 🪩", "spotify_id": "0v8N9oQJ01G4m6xHqYF9eQ"},
        {"title": "Tarkan - Şıkıdım", "note": "Ritmine kapılmadan duramayacağınız unutulmaz bir klasik! ✨", "spotify_id": "2yE4yX8KkI3y6aE10oI5yY"},
        {"title": "Tarkan - Dudu", "note": "Doğu-batı sentezinin en keyifli 2000'ler hitlerinden! 🎶", "spotify_id": "1m0LzqZ9t7YjBfJp6O4C0u"},
        {"title": "Tarkan - Ölürüm Sana", "note": "90'ların sonunu kasıp kavuran yüksek tempolu başyapıt! ⚡", "spotify_id": "4W2T6K6e4zG8Lp4K0N8g4H"},
        {"title": "Tarkan - Kış Güneşi", "note": "Türk pop tarihinin en dokunaklı ve unutulmaz melodilerinden. 🍂", "spotify_id": "0g7y4E6m7K8wX9pL2o3M5k"},
        {"title": "Barış Manço - Kara Sevda", "note": "Gitar riffleri ve enerjisiyle Türk rock tarihinin zirvesi! 🎸", "spotify_id": "2kHqYh0a2GvB0lE0wJ6v3k"},
        {"title": "Barış Manço - Dönence", "note": "Zamansız melodisi ve sözleriyle benzersiz bir yolculuk. 🌌", "spotify_id": "5m8L4k9P0o2M3k7L6N8v9k"},
        {"title": "Barış Manço - Sarı Çizmeli Mehmet Ağa", "note": "Hem düşündüren hem oynatan efsane bir Anadolu rock klasiği! 🌾", "spotify_id": "1x6Y7w8E9p0O1k2M3L4n5O"},
        {"title": "Barış Manço - Gülpembe", "note": "Müzik tarihimizin en naif ve içten bestelerinden. 🌸", "spotify_id": "3e7R8t9Y0u1I2o3P4a5S6d"},
        {"title": "Barış Manço - Alla Beni Pulla Beni", "note": "Neşeli ritmiyle modunuzu anında yerine getirecek bir klasik! 💃", "spotify_id": "7w8E9r0T1y2U3i4O5p6A7s"},
        {"title": "Sezen Aksu - Rakkas", "note": "Neşesi ve coşkusuyla yerinde durdurmayan zamansız bir başyapıt! 🪕", "spotify_id": "4qY1vH2z9N0k8lB7wX3c1v"},
        {"title": "Sezen Aksu - Sarışın", "note": "90'ların en kıpır kıpır Sezen marşlarından biri! ☀️", "spotify_id": "6r7T8y9U0i1O2p3A4s5D6f"},
        {"title": "Sezen Aksu - Hadi Bakalım", "note": "'Hadi bakalım kolay gelsin!' dedirten tam bir enerji bombası! 🚀", "spotify_id": "2y3U4i5O6p7A8s9D0f1G2h"},
        {"title": "Sezen Aksu - Seni Yerler", "note": "Radyolardan hiç düşmeyen eğlenceli ve kıvrak bir Sezen hiti! 🍓", "spotify_id": "3u4I5o6P7a8S9d0F1g2H3j"},
        {"title": "Sezen Aksu - Şinanay", "note": "Ada vapurunda çay içiyormuş gibi hissettiren neşeli bir melodi. 🌊", "spotify_id": "4i5O6p7A8s9D0f1G2h3J4k"},
        {"title": "Mustafa Sandal - Araba", "note": "90'ların efsanevi arabalı klibini ve melodisini hatırlatan hit! 🚗", "spotify_id": "3vL4yH2k9N0m8lB7wX1c5v"},
        {"title": "Mustafa Sandal - Aya Benzer", "note": "O meşhur dans figürlerini anında hatırlatan 90'lar pop klasiği! 🌙", "spotify_id": "5t6Y7u8I9o0P1a2S3d4F5g"},
        {"title": "Mustafa Sandal - Pazara Kadar", "note": "Mezara kadar dedirten 2000'lerin en hareketli şarkılarından! 💃", "spotify_id": "7u8I9o0P1a2S3d4F5g6H7j"},
        {"title": "Sertab Erener - Rengârenk", "note": "Hayat dolu, pozitif ve rengarenk hissettiren harika bir melodi! 🌈", "spotify_id": "1mN0pQ5vK9z2yL4xW8b7vM"},
        {"title": "Sertab Erener - Everyway That I Can", "note": "2003 Eurovision birincimiz, hala ilk günkü gibi enerjik! 🏆", "spotify_id": "8i9O0p1A2s3D4f5G6h7J8k"},
        {"title": "Sertab Erener - Yanarım", "note": "Vokaliyle ve yaylılarıyla büyüleyen zamansız bir eser. 🔥", "spotify_id": "9o0P1a2S3d4F5g6H7j8K9l"},
        {"title": "Kenan Doğulu - Çakkıdı", "note": "Türkçe popun en eğlenceli ve neşeli dans parçalarından biri! 🕶️", "spotify_id": "0p1A2s3D4f5G6h7J8k9L0m"},
        {"title": "Kenan Doğulu - Aşk ile Yap", "note": "Yaptığınız her işe enerji ve neşe katacak pozitif bir parça! 💫", "spotify_id": "1a2S3d4F5g6H7j8K9l0M1n"},
        {"title": "Kenan Doğulu - Shake It Up Şekerim", "note": "Eurovision coşkusunu ve 2000'ler popunu yaşatan harika bir şarkı! 🍭", "spotify_id": "2s3D4f5G6h7J8k9L0m1N2o"},
        {"title": "Nil Karaibrahimgil - Kanatlarım Var Ruhumda", "note": "Özgürlük ve neşe hissini sonuna kadar veren kıpır kıpır bir şarkı! 🕊️", "spotify_id": "3d4F5g6H7j8K9l0M1n2O3p"},
        {"title": "Nil Karaibrahimgil - Pırlanta", "note": "'Tek taşımı kendim aldım' dedirten özgüven dolu bir marş! 💎", "spotify_id": "4f5G6h7J8k9L0m1N2o3P4q"},
        {"title": "MFÖ - Ele Güne Karşı", "note": "Türkçe müzik tarihinin en ikonik ve söylenmesi en keyifli parçası! 🎸", "spotify_id": "5g6H7j8K9l0M1n2O3p4Q5r"},
        {"title": "MFÖ - Ali Desidero", "note": "Mizahi sözleri ve eğlenceli ritmiyle kült bir MFÖ şaheseri! 🥊", "spotify_id": "6h7J8k9L0m1N2o3P4q5R6s"},
        {"title": "MFÖ - Sarı Laleler", "note": "Sabah serinliğinde dinlenecek en naif ve tatlı nostaljik aşk şarkısı. 🌷", "spotify_id": "7j8K9l0M1n2O3p4Q5r6S7t"},
        {"title": "Erkin Koray - Fesuphanallah", "note": "70'lerden günümüze dillerden düşmeyen muhteşem bir melodi! 🪕", "spotify_id": "8k9L0m1N2o3P4q5R6s7T8u"},
        {"title": "Erkin Koray - Şaşkın", "note": "Giriş melodisiyle insanı hemen içine çeken efsanevi bir eser! 🐪", "spotify_id": "9l0M1n2O3p4Q5r6S7t8U9v"},
        {"title": "Erkin Koray - Çöpçüler", "note": "Sokakların hüznünü ve sıcaklığını anlatan unutulmaz bir klasik. 🧹", "spotify_id": "0m1N2o3P4q5R6s7T8u9V0w"},
        {"title": "Candan Erçetin - Yalan", "note": "90'lar sonuna damga vurmuş, melodisi kulaklardan silinmeyen bir eser. 🕯️", "spotify_id": "1n2O3p4Q5r6S7t8U9v0W1x"},
        {"title": "Candan Erçetin - Melek", "note": "Balkan ezgileriyle dinleyeni bambaşka diyarlara götüren bir hit. 🎻", "spotify_id": "2o3P4q5R6s7T8u9V0w1X2y"},
        {"title": "Duman - Her Şeyi Yak", "note": "Sezen Aksu bestesinin Duman yorumuyla rock zirvesine ulaştığı o parça! 🎸", "spotify_id": "3p4Q5r6S7t8U9v0W1x2Y3z"},
        {"title": "Duman - Senden Daha Güzel", "note": "Konserlerde binlerce kişinin tek bir ağızdan söylediği bir marş! 🌟", "spotify_id": "4q5R6s7T8u9V0w1X2y3Z4a"},
        {"title": "Athena - Kafama Göre", "note": "Kafayı dağıtıp anın tadını çıkarmak isteyenlere özel ska-punk enerjisi! 🛹", "spotify_id": "5r6S7t8U9v0W1x2Y3z4A5b"},
        {"title": "Athena - For Real", "note": "Eurovision sahnesini sallayan yerinde duramayan ska klasiği! 🎺", "spotify_id": "6s7T8u9V0w1X2y3Z4a5B6c"},
        {"title": "Athena - Holigan", "note": "Statların ve sokakların asla eskimeyen yüksek tempolu marşı! ⚽", "spotify_id": "7t8U9v0W1x2Y3z4A5b6C7d"},
        {"title": "Mor ve Ötesi - Cambaz", "note": "2000'ler Türkçe alternatif rock müziğinin en güçlü kilometre taşı! 🥁", "spotify_id": "8u9V0w1X2y3Z4a5B6c7D8e"},
        {"title": "Mor ve Ötesi - Bir Derdim Var", "note": "Giriş solosuyla bile tüyleri diken diken eden efsanevi şarkı. 🎸", "spotify_id": "9v0W1x2Y3z4A5b6C7d8E9f"},
        {"title": "Şebnem Ferah - Sil Baştan", "note": "Hayata yeniden başlama gücü veren Türkçe rockın en güçlü vokali! 🦅", "spotify_id": "0w1X2y3Z4a5B6c7D8e9F0g"},
        {"title": "Şebnem Ferah - Yağmurlar", "note": "Duygusal derinliğiyle 90'lardan bu yana dinlenen eşsiz bir beste. 🌧️", "spotify_id": "1x2Y3z4A5b6C7d8E9f0G1h"},
        {"title": "Teoman - Paramparça", "note": "Kelimeleri ve hissiyle dönemin gençliğini özetleyen kült bir klasik. 🍂", "spotify_id": "2y3Z4a5B6c7D8e9F0g1H2i"},
        {"title": "Teoman - Gönülçelen", "note": "Akustik gitarı ve nostaljik hüznüyle Teoman'ın en sevilen parçalarından. 📻", "spotify_id": "3z4A5b6C7d8E9f0G1h2I3j"},
        {"title": "Burak Kut - Benimle Oynama", "note": "90'lar gençlik patlamasının ve pop rüzgarının başlangıç noktası! 🪩", "spotify_id": "4a5B6c7D8e9F0g1H2i3J4k"},
        {"title": "Yonca Evcimik - Abone", "note": "90'lar Türkçe popunun miladı sayılan, enerjisi hiç bitmeyen şarkı! 📟", "spotify_id": "5b6C7d8E9f0G1h2I3j4K5l"},
        {"title": "Hakan Peker - Ateşini Yolla Bana", "note": "Klipleri ve danslarıyla 90'ların en kıpır kıpır nostaljisi! 🔥", "spotify_id": "6c7D8e9F0g1H2i3J4k5L6m"},
        {"title": "Çelik - Hercai", "note": "90'lar aşk şarkılarının en samimi ve unutulmaz melodilerinden. 🌹", "spotify_id": "7d8E9f0G1h2I3j4K5l6M7n"},
        {"title": "İzel-Çelik-Ercan - Dönmelisin", "note": "90'ların başında fırtınalar estiren o efsanevi üçlünün klasiği! 🎙️", "spotify_id": "8e9F0g1H2i3J4k5L6m7N8o"}
    ]

    if "selected_song" not in st.session_state:
        st.session_state.selected_song = random.choice(SONG_LIST)

    song = st.session_state.selected_song
    st.markdown(f"**Öneri:** {song['title']}")
    st.info(song["note"])
    
    # Spotify Oynatıcı Kartı
    st.components.v1.iframe(
        f"https://open.spotify.com/embed/track/{song['spotify_id']}?utm_source=generator&theme=0",
        width=100,
        height=152,
        scrolling=False
    )

    st.caption("Sekmeyi dilediğiniz zaman kapatabilirsiniz.")

# ==========================================
# 5. ADIM: YÖNETİCİ PANELİ & VERİ İNDİRME (SIDEBAR)
# ==========================================
import io

with st.sidebar:
    st.markdown("### 📊 Araştırmacı Paneli")
    admin_password = st.text_input("Yönetici Şifresi:", type="password")
    
    if admin_password == "airesearch2003":
        st.success("Yönetici girişi başarılı!")
        df = database.get_all_data_df()
        st.write(f"**Toplam Katılımcı Sayısı:** {len(df)}")
        st.dataframe(df)
        
        # 1. Düzgün Excel Formatında İndirme (.xlsx)
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Veri_Seti')
        
        st.download_button(
            label="📥 Excel Olarak İndir (.xlsx)",
            data=excel_buffer.getvalue(),
            file_name="arastirma_veriseti.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # 2. Türkiye Excel Uyumlu CSV Formatında İndirme
        csv_data = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 CSV Olarak İndir (.csv)",
            data=csv_data,
            file_name="arastirma_veriseti.csv",
            mime="text/csv"
        )