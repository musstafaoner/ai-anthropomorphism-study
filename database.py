# database.py
import sqlite3
import pandas as pd

DB_NAME = "study_data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE,
            condition TEXT,
            age INTEGER,
            ai_experience TEXT,
            turn_count INTEGER,
            total_input_tokens INTEGER,
            total_output_tokens INTEGER,
            total_tokens INTEGER,
            perceived_anthro_1 INTEGER,
            perceived_anthro_2 INTEGER,
            social_presence_1 INTEGER,
            social_presence_2 INTEGER,
            task_difficulty INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_experiment_data(data: dict):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO responses (
            session_id, condition, age, ai_experience,
            turn_count, total_input_tokens, total_output_tokens, total_tokens,
            perceived_anthro_1, perceived_anthro_2,
            social_presence_1, social_presence_2,
            task_difficulty
        ) VALUES (
            :session_id, :condition, :age, :ai_experience,
            :turn_count, :total_input_tokens, :total_output_tokens, :total_tokens,
            :perceived_anthro_1, :perceived_anthro_2,
            :social_presence_1, :social_presence_2,
            :task_difficulty
        )
    """, data)
    conn.commit()
    conn.close()

def get_all_data_df():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM responses", conn)
    conn.close()
    return df

def clear_all_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM responses")
    conn.commit()
    conn.close()
    
def delete_row_by_id(row_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM responses WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()