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
# 4. ADIM: BİTİŞ EKRANI & ŞARKI ÖNERİSİ HEDİYESİ
# ==========================================
elif st.session_state.step == "finished":
    st.balloons()
    st.success("Tebrikler! Katılımınız başarıyla kaydedildi.")
    st.write("Araştırmamıza sağladığınız değerli katkılar için çok teşekkür ederiz.")
    
    st.write("---")
    st.subheader("🎵 Katkınız İçin Size Özel Şarkı Önerisi")
    
    if "song_recommendation" not in st.session_state:
        with st.spinner("Sizin için özel bir şarkı seçiliyor..."):
            try:
                # Gemini'den hızlıca güzel bir şarkı tavsiyesi isteyelim
                prompt_song = "Bana enerjik, dinlemesi keyifli, popüler veya kaliteli bir şarkı öner. Format: 'Şarkı Adı - Sanatçı' ve 1 cümlelik neden dinlemesi gerektiğine dair eğlenceli bir not olsun."
                res = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt_song
                )
                st.session_state.song_recommendation = res.text
            except Exception:
                st.session_state.song_recommendation = "Daft Punk - Get Lucky 🎶 (Günün enerjisini yükseltmek için harika bir parça!)"
    
    st.info(st.session_state.song_recommendation)
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