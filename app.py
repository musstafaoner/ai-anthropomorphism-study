import io
import os
import random
import uuid
import pandas as pd
import streamlit as st
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
    st.error("API Anahtarı bulunamadı! Lütfen .env dosyasını veya Streamlit Secrets ayarlarını kontrol edin.")
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
    st.session_state.age = 22
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
        Deney yaklaşık **2-3 dakika** sürecektir. Katkılarınız için teşekkür ederiz.
        """
    )
    
    st.info("💡 Testin sonunda yapay zekanın size özel nostaljik bir Türkçe şarkı hediyesi var! 🎧")

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

    # Sohbet geçmişini ekrana yazdır
    for msg in st.session_state.messages:
        role_label = "assistant" if msg["role"] in ["assistant", "model"] else "user"
        with st.chat_message(role_label):
            st.markdown(msg["content"])

    # Kullanıcıdan mesaj alma
    user_input = st.chat_input("Mesajınızı yazın...")

    if user_input:
        # Kullanıcı mesajını kaydet
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.turn_count += 1

        # Sistem talimatını koşula göre belirle
        system_instruction = (
            SYSTEM_PROMPT_HIGH_ANTHRO
            if st.session_state.condition == "High_Anthro"
            else SYSTEM_PROMPT_LOW_ANTHRO
        )

        with st.spinner("Yanıt oluşturuluyor..."):
            try:
                # Gemini SDK formatına uygun mesaj geçmişini hazırla
                contents_payload = [
                    types.Content(
                        role="user" if m["role"] == "user" else "model",
                        parts=[types.Part.from_text(text=m["content"])],
                    )
                    for m in st.session_state.messages
                ]

                # Gemini API Çağrısı
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents_payload,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                        max_output_tokens=600
                    )
                )

                bot_response = response.text or "Bir hata oluştu, lütfen tekrar deneyin."
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
            total_tokens = (
                st.session_state.total_input_tokens + st.session_state.total_output_tokens
            )

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
# 4. ADIM: BİTİŞ EKRANI & ŞARKI HEDİYESİ
# ==========================================
elif st.session_state.step == "finished":
    st.balloons()
    st.success("Tebrikler! Katılımınız başarıyla kaydedildi.")
    st.write("Araştırmamıza sağladığınız değerli katkılar için çok teşekkür ederiz.")
    
    st.write("---")
    st.subheader("🎵 Katkınız İçin Size Özel Nostaljik Türkçe Şarkı Hediyesi")

    SONG_LIST = [
        {"title": "Tarkan - Kuzu Kuzu", "note": "2000'lerin efsanevi zilli klasiği! 🪩"},
        {"title": "Tarkan - Şıkıdım (Hepsi Senin mi?)", "note": "Ritmine kapılmadan duramayacağınız unutulmaz bir Tarkan klasiği! ✨"},
        {"title": "Tarkan - Dudu", "note": "Doğu-batı sentezinin en keyifli 2000'ler hitlerinden! 🎶"},
        {"title": "Tarkan - Ölürüm Sana", "note": "90'ların sonunu kasıp kavuran yüksek tempolu başyapıt! ⚡"},
        {"title": "Tarkan - Kış Güneşi", "note": "Türk pop tarihinin en dokunaklı ve unutulmaz melodilerinden. 🍂"},
        {"title": "Barış Manço - Kara Sevda", "note": "Gitar riffleri ve enerjisiyle Türk rock tarihinin zirvesi! 🎸"},
        {"title": "Barış Manço - Dönence", "note": "Zamansız melodisi ve sözleriyle benzersiz bir yolculuk. 🌌"},
        {"title": "Barış Manço - Sarı Çizmeli Mehmet Ağa", "note": "Hem düşündüren hem oynatan efsane bir Anadolu rock klasiği! 🌾"},
        {"title": "Barış Manço - Gülpembe", "note": "Müzik tarihimizin en naif ve içten bestelerinden. 🌸"},
        {"title": "Barış Manço - Alla Beni Pulla Beni", "note": "Neşeli ritmiyle modunuzu anında yerine getirecek bir klasik! 💃"},
        {"title": "Sezen Aksu - Rakkas", "note": "Neşesi ve coşkusuyla yerinde durdurmayan zamansız bir başyapıt! 🪕"},
        {"title": "Sezen Aksu - Sarışın", "note": "90'ların en kıpır kıpır Sezen marşlarından biri! ☀️"},
        {"title": "Sezen Aksu - Hadi Bakalım", "note": "'Hadi bakalım kolay gelsin!' dedirten tam bir enerji bombası! 🚀"},
        {"title": "Sezen Aksu - Seni Yerler", "note": "Radyolardan hiç düşmeyen eğlenceli ve kıvrak bir Sezen hiti! 🍓"},
        {"title": "Sezen Aksu - Şinanay", "note": "Ada vapurunda çay içiyormuş gibi hissettiren neşeli bir melodi. 🌊"},
        {"title": "Mustafa Sandal - Araba", "note": "90'ların efsanevi arabalı klibini ve melodisini hatırlatan hit! 🚗"},
        {"title": "Mustafa Sandal - Aya Benzer", "note": "O meşhur dans figürlerini anında hatırlatan 90'lar pop klasiği! 🌙"},
        {"title": "Mustafa Sandal - Pazara Kadar", "note": "Mezara kadar dedirten 2000'lerin en hareketli şarkılarından! 💃"},
        {"title": "Sertab Erener - Rengârenk", "note": "Hayat dolu, pozitif ve rengarenk hissettiren harika bir melodi! 🌈"},
        {"title": "Sertab Erener - Everyway That I Can", "note": "2003 Eurovision birincimiz, hala ilk günkü gibi enerjik! 🏆"},
        {"title": "Sertab Erener - Yanarım", "note": "Vokaliyle ve yaylılarıyla büyüleyen zamansız bir eser. 🔥"},
        {"title": "Kenan Doğulu - Çakkıdı", "note": "Türkçe popun en eğlenceli ve neşeli dans parçalarından biri! 🕶️"},
        {"title": "Kenan Doğulu - Aşk ile Yap", "note": "Yaptığınız her işe enerji ve neşe katacak pozitif bir parça! 💫"},
        {"title": "Kenan Doğulu - Shake It Up Şekerim", "note": "Eurovision coşkusunu ve 2000'ler popunu yaşatan harika bir şarkı! 🍭"},
        {"title": "Nil Karaibrahimgil - Kanatlarım Var Ruhumda", "note": "Özgürlük ve neşe hissini sonuna kadar veren kıpır kıpır bir şarkı! 🕊️"},
        {"title": "Nil Karaibrahimgil - Pırlanta", "note": "'Tek taşımı kendim aldım' dedirten özgüven dolu bir marş! 💎"},
        {"title": "MFÖ - Ele Güne Karşı", "note": "Türkçe müzik tarihinin en ikonik ve söylenmesi en keyifli parçası! 🎸"},
        {"title": "MFÖ - Ali Desidero", "note": "Mizahi sözleri ve eğlenceli ritmiyle kült bir MFÖ şaheseri! 🥊"},
        {"title": "MFÖ - Sarı Laleler", "note": "Sabah serinliğinde dinlenecek en naif ve tatlı nostaljik aşk şarkısı. 🌷"},
        {"title": "Erkin Koray - Fesuphanallah", "note": "70'lerden günümüze dillerden düşmeyen muhteşem bir melodi! 🪕"},
        {"title": "Erkin Koray - Şaşkın", "note": "Giriş melodisiyle insanı hemen içine çeken efsanevi bir eser! 🐪"},
        {"title": "Erkin Koray - Çöpçüler", "note": "Sokakların hüznünü ve sıcaklığını anlatan unutulmaz bir klasik. 🧹"},
        {"title": "Candan Erçetin - Yalan", "note": "90'lar sonuna damga vurmuş, melodisi kulaklardan silinmeyen bir eser. 🕯️"},
        {"title": "Candan Erçetin - Melek", "note": "Balkan ezgileriyle dinleyeni bambaşka diyarlara götüren bir hit. 🎻"},
        {"title": "Duman - Her Şeyi Yak", "note": "Sezen Aksu bestesinin Duman yorumuyla rock zirvesine ulaştığı o parça! 🎸"},
        {"title": "Duman - Senden Daha Güzel", "note": "Konserlerde binlerce kişinin tek bir ağızdan söylediği bir marş! 🌟"},
        {"title": "Athena - Kafama Göre", "note": "Kafayı dağıtıp anın tadını çıkarmak isteyenlere özel ska-punk enerjisi! 🛹"},
        {"title": "Athena - For Real", "note": "Eurovision sahnesini sallayan yerinde duramayan ska klasiği! 🎺"},
        {"title": "Athena - Holigan", "note": "Statların ve sokakların asla eskimeyen yüksek tempolu marşı! ⚽"},
        {"title": "Mor ve Ötesi - Cambaz", "note": "2000'ler Türkçe alternatif rock müziğinin en güçlü kilometre taşı! 🥁"},
        {"title": "Mor ve Ötesi - Bir Derdim Var", "note": "Giriş solosuyla bile tüyleri diken diken eden efsanevi şarkı. 🎸"},
        {"title": "Şebnem Ferah - Sil Baştan", "note": "Hayata yeniden başlama gücü veren Türkçe rockın en güçlü vokali! 🦅"},
        {"title": "Şebnem Ferah - Yağmurlar", "note": "Duygusal derinliğiyle 90'lardan bu yana dinlenen eşsiz bir beste. 🌧️"},
        {"title": "Teoman - Paramparça", "note": "Kelimeleri ve hissiyle dönemin gençliğini özetleyen kült bir klasik. 🍂"},
        {"title": "Teoman - Gönülçelen", "note": "Akustik gitarı ve nostaljik hüznüyle Teoman'ın en sevilen parçalarından. 📻"},
        {"title": "Burak Kut - Benimle Oynama", "note": "90'lar gençlik patlamasının ve pop rüzgarının başlangıç noktası! 🪩"},
        {"title": "Yonca Evcimik - Abone", "note": "90'lar Türkçe popunun miladı sayılan, enerjisi hiç bitmeyen şarkı! 📟"},
        {"title": "Hakan Peker - Ateşini Yolla Bana", "note": "Klipleri ve danslarıyla 90'ların en kıpır kıpır nostaljisi! 🔥"},
        {"title": "Çelik - Hercai", "note": "90'lar aşk şarkılarının en samimi ve unutulmaz melodilerinden. 🌹"},
        {"title": "İzel-Çelik-Ercan - Dönmelisin", "note": "90'ların başında fırtınalar estiren o efsanevi üçlünün klasiği! 🎙️"}
    ]

    if "selected_song" not in st.session_state:
        st.session_state.selected_song = random.choice(SONG_LIST)

    song = st.session_state.selected_song
    
    # Şarkı Kartı Tasarımı
    st.markdown(
        f"""
        <div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border-left: 6px solid #10b981; margin: 15px 0;">
            <h3 style="color: #f8fafc; margin-top: 0;">🎧 {song['title']}</h3>
            <p style="color: #cbd5e1; font-size: 15px; margin-bottom: 15px;">{song['note']}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    query_encoded = song['title'].replace(" ", "+")
    spotify_search_url = f"https://open.spotify.com/search/{query_encoded}"
    youtube_search_url = f"https://www.youtube.com/results?search_query={query_encoded}"

    col1, col2 = st.columns(2)
    with col1:
        st.link_button("🟢 Spotify'da Dinle", spotify_search_url, use_container_width=True)
    with col2:
        st.link_button("🔴 YouTube'da Dinle", youtube_search_url, use_container_width=True)

    st.caption("Sekmeyi dilediğiniz zaman kapatabilirsiniz.")


# ==========================================
# 5. ADIM: YÖNETİCİ PANELİ & VERİ İNDİRME (SIDEBAR)
# ==========================================
with st.sidebar:
    st.markdown("### 📊 Araştırmacı Paneli")
    admin_password = st.text_input("Yönetici Şifresi:", type="password")
    
    if admin_password == "admin123":
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

        # 2. CSV İndirme
        csv_data = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 CSV Olarak İndir (.csv)",
            data=csv_data,
            file_name="arastirma_veriseti.csv",
            mime="text/csv"
        )

        # 3. Satır Satır Silme Bölümü
        st.write("---")
        st.markdown("#### 🗑️ Satır Sil")
        if not df.empty:
            selected_id = st.selectbox("Silinecek Kayıt ID:", options=df["id"].tolist())
            if st.button("Seçili Satırı Sil", type="secondary"):
                database.delete_row_by_id(selected_id)
                st.warning(f"ID: {selected_id} olan kayıt silindi!")
                st.rerun()

        # 4. Tümünü Silme Bölümü
        if st.button("⚠️ Tüm Verileri Sıfırla", type="secondary"):
            database.clear_all_data()
            st.warning("Tüm veriler temizlendi!")
            st.rerun()