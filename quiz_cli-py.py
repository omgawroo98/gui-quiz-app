#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, random, sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

# ---------------------------
# Laden & Normalisieren
# ---------------------------
def load_quiz(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        sys.exit(f"❌ Fehler beim Laden der Datei: {e}")

    questions = []
    for q in data:
        if not isinstance(q, dict) or "question" not in q or "choices" not in q:
            continue
        answer = q.get("answer", "").strip().upper()
        if len(answer) == 1:
            idx = ord(answer) - ord("A")
        else:
            try:
                idx = int(answer)
            except ValueError:
                continue
        questions.append({
            "question": q["question"],
            "choices": q["choices"],
            "answer_idx": idx,
            "explanation": q.get("explanation", "")
        })
    return questions

# ---------------------------
# GUI-Klasse
# ---------------------------
class QuizApp(tk.Tk):
    def __init__(self, questions):
        super().__init__()
        self.title("🧠 Usability & UX Quiz")
        self.geometry("800x500")
        self.configure(bg="#f9fafb")

        self.questions = random.sample(questions, len(questions))
        self.total = len(self.questions)
        self.current = 0
        self.correct = 0
        self.user_answers = []

        # Widgets
        self.question_label = tk.Label(self, text="", wraplength=750,
                                       font=("Helvetica", 15, "bold"), bg="#f9fafb", justify="left")
        self.question_label.pack(pady=25)

        self.buttons_frame = tk.Frame(self, bg="#f9fafb")
        self.buttons_frame.pack(pady=10)

        self.status_label = tk.Label(self, text="", font=("Helvetica", 12), bg="#f9fafb")
        self.status_label.pack(side="bottom", pady=15)

        self.show_question()

    def show_question(self):
        """Zeigt aktuelle Frage mit Antwortbuttons"""
        q = self.questions[self.current]
        self.question_label.config(text=f"Frage {self.current+1}/{self.total}:\n\n{q['question']}")
        for widget in self.buttons_frame.winfo_children():
            widget.destroy()

        for i, choice in enumerate(q["choices"]):
            btn = tk.Button(
                self.buttons_frame,
                text=f"{chr(65+i)}) {choice}",
                font=("Helvetica", 13),
                width=70,
                pady=6,
                bg="#e5e7eb",
                relief="raised",
                bd=2,
                command=lambda idx=i: self.submit_answer(idx)
            )
            btn.pack(pady=5)

        self.status_label.config(
            text=f"Punkte: {self.correct} / {self.current}   |   Verbleibend: {self.total - self.current}"
        )

    def submit_answer(self, idx):
        """Verarbeite Antwortauswahl"""
        q = self.questions[self.current]
        correct = (idx == q["answer_idx"])
        self.user_answers.append((q, idx, correct))
        if correct:
            self.correct += 1
        self.current += 1

        if self.current < self.total:
            self.show_question()
        else:
            self.show_results()

    def show_results(self):
        """Endauswertung"""
        for widget in self.winfo_children():
            widget.destroy()

        pct = (self.correct / self.total) * 100
        result_text = f"🏁 Ergebnis: {self.correct}/{self.total} richtig ({pct:.1f}%)"
        tk.Label(self, text=result_text, font=("Helvetica", 16, "bold"), bg="#f9fafb").pack(pady=20)

        # Review-Bereich
        review_frame = tk.Frame(self, bg="#f9fafb")
        review_frame.pack(pady=10)

        for i, (q, user_idx, correct) in enumerate(self.user_answers, start=1):
            status = "✅" if correct else "❌"
            qtext = f"{status} {i}. {q['question']}\n  Deine Antwort: {q['choices'][user_idx]}"
            qtext += f"\n  Richtige Antwort: {q['choices'][q['answer_idx']]}"
            if q.get("explanation"):
                qtext += f"\n  💡 {q['explanation']}"
            lbl = tk.Label(review_frame, text=qtext, wraplength=750, justify="left",
                           bg="#f9fafb", anchor="w", font=("Helvetica", 11))
            lbl.pack(pady=8, anchor="w")

        tk.Button(self, text="Quiz schließen", font=("Helvetica", 13, "bold"),
                  bg="#d1fae5", command=self.destroy).pack(pady=20)

# ---------------------------
# Hauptprogramm
# ---------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GUI-Quiz zu Usability & Softwareergonomie")
    parser.add_argument("file", help="Pfad zur JSON-Datei mit Quizfragen")
    args = parser.parse_args()

    questions = load_quiz(args.file)
    if not questions:
        sys.exit("❌ Keine gültigen Fragen gefunden.")
    app = QuizApp(questions)
    app.mainloop()
