#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import copy
import json, sys, random
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk


APP_TITLE = "🧠 Usability & Softwareergonomie – Quiz"

def _to_index_set(answer, n_choices):
    """
    Normalisiert 'answer' zu einer Menge von Indizes (0..n-1).
    Erlaubt:
      - "B" oder "b"
      - 1-basige oder 0-basige Zahlen
      - Listen aus obigen Typen, gemischt
    """
    def one_to_idx(x):
        # einzelwert -> idx (oder None)
        if isinstance(x, str):
            a = x.strip().upper()
            if len(a) == 1 and "A" <= a <= chr(ord("A")+n_choices-1):
                return ord(a) - ord("A")
            # Versuch: Zahl als String
            try:
                xi = int(a)
                if 1 <= xi <= n_choices:  # 1-basiert
                    return xi - 1
                if 0 <= xi < n_choices:   # 0-basiert
                    return xi
            except Exception:
                return None
        else:
            try:
                xi = int(x)
                if 1 <= xi <= n_choices:
                    return xi - 1
                if 0 <= xi < n_choices:
                    return xi
            except Exception:
                return None
        return None

    idxs = set()
    if isinstance(answer, (list, tuple, set)):
        for a in answer:
            idx = one_to_idx(a)
            if idx is None:
                raise ValueError(f"Ungültiger Antwortwert in Liste: {a!r}")
            idxs.add(idx)
    else:
        idx = one_to_idx(answer)
        if idx is None:
            raise ValueError(f"Ungültiger Antwortwert: {answer!r}")
        idxs.add(idx)

    if not idxs:
        raise ValueError("Leere Lösungsmenge ist nicht erlaubt.")
    if any(not (0 <= i < n_choices) for i in idxs):
        raise ValueError("Lösungsindex außerhalb der Choice-Grenzen.")

    return idxs

def load_questions(path):
    """Liest JSON (eine Liste von Fragen-Objekten) und normalisiert.
    Felder:
      - section: str
      - question: str
      - choices: [str, ...]
      - answer: str|int|[str|int,...]
      - explanation: str (optional)
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Erwartet wird eine nicht-leere Liste von Fragen-Objekten.")

    norm = []
    for i, q in enumerate(data, start=1):
        if not isinstance(q, dict):
            raise ValueError(f"Frage #{i} ist kein Objekt.")
        section = q.get("section") or "Allgemein"
        question = q.get("question")
        choices = q.get("choices")
        answer = q.get("answer")
        explanation = q.get("explanation", "")

        if not question or not isinstance(choices, list) or len(choices) < 2:
            raise ValueError(f"Frage #{i}: 'question' + mind. 2 'choices' erforderlich.")
        if len(choices) > 26:
            raise ValueError(f"Frage #{i}: max. 26 Antwortoptionen (A–Z).")

        answer_idx_set = _to_index_set(answer, len(choices))
        is_multi = len(answer_idx_set) > 1

        norm.append({
            "section": str(section),
            "question": str(question),
            "choices": [str(c) for c in choices],
            # Kompatibel weiterverwenden, aber intern immer Set prüfen:
            "answer_idx_set": set(answer_idx_set),
            "is_multi": bool(is_multi),
            "explanation": str(explanation),
        })
    return norm

class QuizApp(tk.Tk):
    def __init__(self, all_questions):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1080x800")
        self.configure(bg="#f8fafc")
        self.minsize(800,400)

        # ttk-Style
        self.style = ttk.Style(self)
        try:
            self.style.theme_use(self.style.theme_use())
        except Exception:
            pass
        self.style.configure(
            "TCheckbutton",
            background="#f8fafc",
            font=("Helvetica", 11),
            padding=(2, 2)
        )

        # Daten
        self.all_questions = all_questions
        self.sections = self._collect_sections(all_questions)
        self.current_section = None
        self.questions = []
        self.total = 0
        self.idx = 0
        self.correct = 0
        self.user_answers = []
        self.shuffle = True
        self.shuffle_choices = True
        self.allow_skip = True
        self.show_explanations_end = True

        # Auswahl-State für aktuelle Frage
        self._radio_var = None              # IntVar für Single
        self._check_vars = []               # List[BooleanVar] für Multi

        # Views
        self.container = tk.Frame(self, bg="#f8fafc")
        self.container.pack(fill="both", expand=True)

        self._build_menu_view()

    # ---------- Daten & Utils ----------
    @staticmethod
    def _collect_sections(items):
        sections = {}
        for q in items:
            sec = q.get("section", "Allgemein")
            sections.setdefault(sec, 0)
            sections[sec] += 1
        return sections

    def _shuffle_question_choices(self, q):
        """
        Shuffle der Antwortoptionen inkl. Remapping einer Lösungs-MENGE.
        """
        choices = q["choices"]
        answer_set = q["answer_idx_set"]

        indices = list(range(len(choices)))
        random.shuffle(indices)

        new_choices = [choices[i] for i in indices]
        # altes->neues Mapping: alter Index -> neue Position
        inv = {old_i: new_pos for new_pos, old_i in enumerate(indices)}
        new_answer_set = {inv[i] for i in answer_set}

        new_q = dict(q)
        new_q["choices"] = new_choices
        new_q["answer_idx_set"] = new_answer_set
        return new_q

    def _reset_session(self, section):
        self.current_section = section
        base = [copy.deepcopy(q) for q in self.all_questions if q["section"] == section]

        if self.shuffle:
            random.shuffle(base)
        if getattr(self, "shuffle_choices", True):
            base = [self._shuffle_question_choices(q) for q in base]

        self.questions = base
        self.total = len(self.questions)
        self.idx = 0
        self.correct = 0
        self.user_answers = []

    # ---------- Views ----------
    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def _build_menu_view(self):
        self._clear()
        header = tk.Label(self.container, text="Wähle einen Abschnitt",
                          font=("Helvetica", 20, "bold"), bg="#f8fafc")
        header.pack(pady=16)

        opts = tk.Frame(self.container, bg="#f8fafc")
        opts.pack(fill="x", padx=12, pady=4)

        self.shuffle_var = tk.BooleanVar(value=self.shuffle)
        self.shuffle_choices_var = tk.BooleanVar(value=self.shuffle_choices)
        self.skip_var = tk.BooleanVar(value=self.allow_skip)
        self.expl_var = tk.BooleanVar(value=self.show_explanations_end)

        cb1 = ttk.Checkbutton(opts, text="Fragen mischen", variable=self.shuffle_var, style="TCheckbutton")
        cb2 = ttk.Checkbutton(opts, text="Antwortoptionen mischen", variable=self.shuffle_choices_var, style="TCheckbutton")
        cb3 = ttk.Checkbutton(opts, text="Überspringen erlauben", variable=self.skip_var, style="TCheckbutton")
        cb4 = ttk.Checkbutton(opts, text="Erklärungen im Review anzeigen", variable=self.expl_var, style="TCheckbutton")

        cb1.grid(row=0, column=0, sticky="w", padx=(0, 16))
        cb2.grid(row=0, column=1, sticky="w", padx=(0, 16))
        cb3.grid(row=0, column=2, sticky="w", padx=(0, 16))
        cb4.grid(row=0, column=3, sticky="w", padx=(0, 0))
        for i in range(4):
            opts.grid_columnconfigure(i, weight=1, uniform="opts")

        grid = tk.Frame(self.container, bg="#f8fafc")
        grid.pack(pady=16, padx=12, fill="both", expand=True)

        r, c = 0, 0
        for sec, count in sorted(self.sections.items(), key=lambda x: x[0].lower()):
            card = tk.Button(
                grid,
                text=f"{sec}\n({count} Fragen)",
                font=("Helvetica", 14, "bold"),
                width=26, height=4,
                bg="#e5e7eb", bd=2, relief="raised",
                command=lambda s=sec: self.start_section(s)
            )
            card.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")
            c += 1
            if c >= 3:
                r += 1
                c = 0

        footer = tk.Label(self.container, text="Tipp: Du kannst jederzeit mit „Zurück zum Menü“ abbrechen.",
                          font=("Helvetica", 10), bg="#f8fafc")
        footer.pack(pady=8)

    def start_section(self, section):
        self.shuffle = self.shuffle_var.get()
        self.shuffle_choices = self.shuffle_choices_var.get()
        self.allow_skip = self.skip_var.get()
        self.show_explanations_end = self.expl_var.get()

        self._reset_session(section)
        if self.total == 0:
            messagebox.showinfo("Leer", f"Keine Fragen in Abschnitt: {section}")
            return
        self._build_quiz_view()
        self._render_question()

    def _build_quiz_view(self):
        self._clear()
        top = tk.Frame(self.container, bg="#f8fafc")
        top.pack(fill="x", pady=(12, 2))

        self.progress = tk.Label(top, text="", font=("Helvetica", 12, "bold"), bg="#f8fafc")
        self.progress.pack(side="left", padx=12)

        tk.Button(top, text="Zurück zum Menü", command=self._build_menu_view, bg="#f3f4f6").pack(side="right", padx=12)

        self.q_label = tk.Label(self.container, text="", wraplength=880, justify="left",
                                font=("Helvetica", 16, "bold"), bg="#f8fafc")
        self.q_label.pack(pady=18, anchor="w", padx=20)

        self.multi_hint = tk.Label(self.container, text="", font=("Helvetica", 11, "italic"), bg="#f8fafc")
        self.multi_hint.pack(pady=(0,6), anchor="w", padx=22)

        self.choices_frame = tk.Frame(self.container, bg="#f8fafc")
        self.choices_frame.pack(pady=4)

        # Submit / Skip
        btns = tk.Frame(self.container, bg="#f8fafc")
        btns.pack(pady=10)
        self.submit_btn = tk.Button(btns, text="Prüfen / Senden", bg="#dbeafe", command=self._on_submit_clicked)
        self.submit_btn.grid(row=0, column=0, padx=6)
        self.skip_btn = tk.Button(btns, text="Überspringen", bg="#f3f4f6", command=self._on_skip_clicked)
        self.skip_btn.grid(row=0, column=1, padx=6)

        self.status = tk.Label(self.container, text="", font=("Helvetica", 12), bg="#f8fafc")
        self.status.pack(pady=8)

    def _render_question(self):
        q = self.questions[self.idx]
        self.progress.config(text=f"Abschnitt: {self.current_section}   •   Frage {self.idx+1}/{self.total}")
        self.q_label.config(text=q["question"])
        self.multi_hint.config(
            text="Mehrfachantworten möglich – wähle alle zutreffenden Optionen." if q["is_multi"] else ""
        )

        for w in self.choices_frame.winfo_children():
            w.destroy()

        self._radio_var = None
        self._check_vars = []

        if q["is_multi"]:
            # Checkbuttons
            for i, choice in enumerate(q["choices"]):
                var = tk.BooleanVar(value=False)
                self._check_vars.append(var)
                cb = ttk.Checkbutton(self.choices_frame,
                                     text=f"{chr(65+i)}) {choice}",
                                     variable=var, style="TCheckbutton")
                cb.pack(pady=6, padx=20, anchor="w")
        else:
            # Radiobuttons
            self._radio_var = tk.IntVar(value=-1)
            for i, choice in enumerate(q["choices"]):
                rb = tk.Radiobutton(self.choices_frame,
                                    text=f"{chr(65+i)}) {choice}",
                                    variable=self._radio_var, value=i,
                                    font=("Helvetica", 13),
                                    bg="#f8fafc", anchor="w", justify="left")
                rb.pack(pady=6, padx=20, anchor="w")

        self.skip_btn.configure(state=("normal" if self.allow_skip else "disabled"))
        self.status.config(text=f"Punkte: {self.correct} / {self.idx}   •   Verbleibend: {self.total - self.idx}")

    def _collect_user_selection(self):
        q = self.questions[self.idx]
        if q["is_multi"]:
            sel = {i for i, var in enumerate(self._check_vars) if var.get()}
            return sel
        else:
            v = self._radio_var.get() if self._radio_var is not None else -1
            return set() if v == -1 else {v}

    def _on_submit_clicked(self):
        q = self.questions[self.idx]
        sel = self._collect_user_selection()

        # Keine Auswahl -> als Skip behandeln, wenn erlaubt
        if not sel:
            if self.allow_skip:
                self.user_answers.append((q, None, False))
                self._advance()
                return
            else:
                messagebox.showinfo("Hinweis", "Bitte eine Option auswählen (oder 'Überspringen' aktivieren).")
                return

        is_correct = (sel == q["answer_idx_set"])
        if is_correct:
            self.correct += 1
        self.user_answers.append((q, sel, is_correct))
        self._advance()

    def _on_skip_clicked(self):
        q = self.questions[self.idx]
        self.user_answers.append((q, None, False))
        self._advance()

    def _advance(self):
        self.idx += 1
        if self.idx < self.total:
            self._render_question()
        else:
            self._show_results()

    def _idx_set_to_letters(self, idx_set, choices_len):
        return ", ".join(sorted(chr(65+i) for i in idx_set)) if idx_set else "—"

    def _choices_text_from_idx_set(self, idx_set, q):
        if not idx_set:
            return "—"
        parts = []
        for i in sorted(idx_set):
            parts.append(f"{chr(65+i)}) {q['choices'][i]}")
        return ", ".join(parts)

    def _show_results(self):
        # Ergebnisansicht
        for w in self.container.winfo_children():
            w.destroy()

        pct = (self.correct / self.total * 100.0) if self.total else 0.0
        tk.Label(self.container, text=f"🏁 Ergebnis: {self.correct}/{self.total} richtig ({pct:.1f} %)",
                 font=("Helvetica", 18, "bold"), bg="#f8fafc").pack(pady=16)

        review = tk.Frame(self.container, bg="#f8fafc")
        review.pack(fill="both", expand=True, padx=20, pady=6)

        canvas = tk.Canvas(review, bg="#f8fafc", highlightthickness=0)
        scrollbar = tk.Scrollbar(review, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#f8fafc")
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_cfg(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_cfg)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for i, (q, user_sel, ok) in enumerate(self.user_answers, start=1):
            status = "✅" if ok else ("⏭️" if (user_sel is None) else "❌")
            block = tk.Frame(inner, bg="#ffffff", bd=1, relief="solid")
            block.pack(fill="x", pady=6)

            correct_txt = self._choices_text_from_idx_set(q["answer_idx_set"], q)
            if user_sel is None:
                user_txt = "— (übersprungen)"
            else:
                user_txt = self._choices_text_from_idx_set(user_sel, q)

            txt = f"{status} {i}. {q['question']}\n"
            txt += f"   Deine Antwort: {user_txt}\n"
            txt += f"   Richtig:       {correct_txt}"
            if self.show_explanations_end and q.get("explanation"):
                txt += f"\n   💡 {q['explanation']}"

            lbl = tk.Label(block, text=txt, justify="left", anchor="w",
                           font=("Helvetica", 11), bg="#ffffff", wraplength=880)
            lbl.pack(padx=10, pady=8, anchor="w")

        btns = tk.Frame(self.container, bg="#f8fafc")
        btns.pack(pady=12)
        tk.Button(btns, text="Abschnitt neu starten", bg="#d1fae5",
                  command=lambda: self.start_section(self.current_section)).grid(row=0, column=0, padx=8)
        tk.Button(btns, text="Zurück zum Menü", bg="#f3f4f6",
                  command=self._build_menu_view).grid(row=0, column=1, padx=8)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="GUI für gemeinsames Quiz mit Abschnitten")
    parser.add_argument("file", help="Pfad zur JSON-Datei mit allen Fragen (mehrere Abschnitte)")
    args = parser.parse_args()

    try:
        all_questions = load_questions(args.file)
    except Exception as e:
        sys.exit(f"❌ Konnte Datei nicht lesen/parsen: {e}")

    app = QuizApp(all_questions)
    app.mainloop()

if __name__ == "__main__":
    main()
