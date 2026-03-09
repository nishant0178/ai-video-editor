import customtkinter as ctk
from tkinter import messagebox
import threading
import os

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

VOICES = {
    "Christopher  —  Deep & Dramatic": "en-US-ChristopherNeural",
    "Guy  —  Clear & Confident":       "en-US-GuyNeural",
    "Ryan  —  British Authority":      "en-GB-RyanNeural",
    "Eric  —  Energetic":              "en-US-EricNeural",
}


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class AIVideoEditor(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Video Editor")
        self.geometry("780x360")
        self.resizable(False, False)
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="AI Video Editor",
                     font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(30, 4))
        ctk.CTkLabel(self, text="Create Instagram Reels from your scripts",
                     font=ctk.CTkFont(size=13), text_color="gray").pack()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=28)

        cards = [
            ("Comics News",        "Latest Marvel, DC, Anime & Manhwa",  self.run_comics_news),
            ("Script to Video",    "Image slideshow with voiceover",      self.run_script_to_video),
            ("Script to AI Video", "AI-generated cinematic video clips",  self.run_script_to_ai_video),
        ]

        for col, (title, desc, cmd) in enumerate(cards):
            card = ctk.CTkFrame(btn_frame, width=230, height=110, corner_radius=8)
            card.grid(row=0, column=col, padx=8)
            card.grid_propagate(False)

            ctk.CTkLabel(card, text=title,
                         font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(18, 3))
            ctk.CTkLabel(card, text=desc,
                         font=ctk.CTkFont(size=11), text_color="gray",
                         wraplength=200).pack(padx=12)
            ctk.CTkButton(card, text="Open", width=90, height=28,
                          font=ctk.CTkFont(size=12),
                          command=cmd).pack(pady=(8, 0))

        self.status_label = ctk.CTkLabel(self, text="Ready",
                                         font=ctk.CTkFont(size=12), text_color="gray")
        self.status_label.pack(pady=(4, 4))

        self.progress = ctk.CTkProgressBar(self, width=680)
        self.progress.pack(padx=50)
        self.progress.set(0)

    def set_status(self, msg):   self.status_label.configure(text=msg)
    def set_progress(self, val): self.progress.set(val)

    def run_in_thread(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def progress_cb(self, msg, val):
        self.after(0, lambda: self.set_status(msg))
        self.after(0, lambda: self.set_progress(val))

    def run_comics_news(self):
        ComicsNewsDialog(self).grab_set()

    def run_script_to_video(self):
        ScriptToVideoDialog(self).grab_set()

    def start_script_to_video(self, topic, script, voiceover, voice):
        self.run_in_thread(lambda: self._do_script_to_video(topic, script, voiceover, voice))

    def _do_script_to_video(self, topic, script, voiceover, voice):
        from features.script_to_video import create_reel
        from utils.file_handler import get_output_path
        output = get_output_path(suffix="_reel")
        try:
            create_reel(topic, script, output, voiceover=voiceover,
                        voice=voice, progress_cb=self.progress_cb)
            self.after(0, lambda: self.set_status("Reel saved to Desktop!"))
            self.after(0, lambda: messagebox.showinfo("Done", f"Reel saved:\n{output}"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda msg=err: self.set_status(f"Error: {msg}"))
            self.after(0, lambda msg=err: messagebox.showerror("Error", msg))

    def run_script_to_ai_video(self):
        ScriptToAIVideoDialog(self).grab_set()

    def start_script_to_ai_video(self, topic, script, voice, api_token):
        self.run_in_thread(lambda: self._do_script_to_ai_video(topic, script, voice, api_token))

    def _do_script_to_ai_video(self, topic, script, voice, api_token):
        from features.kling_video import create_ai_reel
        from utils.file_handler import get_output_path
        output = get_output_path(suffix="_ai_reel")
        try:
            create_ai_reel(topic, script, output, voice=voice,
                           api_token=api_token, progress_cb=self.progress_cb)
            self.after(0, lambda: self.set_status("AI Reel saved to Desktop!"))
            self.after(0, lambda: messagebox.showinfo("Done", f"AI Reel saved:\n{output}"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda msg=err: self.set_status(f"Error: {msg}"))
            self.after(0, lambda msg=err: messagebox.showerror("Error", msg))


# ---------------------------------------------------------------------------
# Script to Video
# ---------------------------------------------------------------------------

class ScriptToVideoDialog(ctk.CTkToplevel):
    def __init__(self, parent, prefill_topic="", prefill_script=""):
        super().__init__(parent)
        self.parent = parent
        self._prefill_topic  = prefill_topic
        self._prefill_script = prefill_script
        self.title("Script to Video")
        self.geometry("600x560")
        self.resizable(False, False)
        self._build_ui()

    def _build_ui(self):
        ctk.CTkButton(self, text="← Back", width=70, height=26,
                      fg_color="transparent", hover_color="#2a2a2a",
                      font=ctk.CTkFont(size=12), text_color="gray",
                      anchor="w", command=self.destroy
                      ).pack(anchor="w", padx=16, pady=(12, 0))

        ctk.CTkLabel(self, text="Script to Video",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(6, 2))
        ctk.CTkLabel(self, text="Fetches images automatically. Adds voiceover and subtitles.",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 16))

        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="x", padx=30)

        ctk.CTkLabel(f, text="Topic", font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").pack(fill="x")
        self.topic_entry = ctk.CTkEntry(f, height=36,
                                        placeholder_text='e.g. Spider-Man Marvel comics',
                                        font=ctk.CTkFont(size=13))
        self.topic_entry.pack(fill="x", pady=(4, 12))
        if self._prefill_topic:
            self.topic_entry.insert(0, self._prefill_topic)

        ctk.CTkLabel(f, text="Script", font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").pack(fill="x")
        self.textbox = ctk.CTkTextbox(f, height=160, font=ctk.CTkFont(size=13))
        self.textbox.pack(fill="x", pady=(4, 12))
        default = self._prefill_script or "Spider-Man has defeated Thanos not once, but THREE times in the comics. Here's why that matters..."
        self.textbox.insert("0.0", default)

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))
        row.columnconfigure(0, weight=3)
        row.columnconfigure(1, weight=1)

        vc = ctk.CTkFrame(row, fg_color="transparent")
        vc.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkLabel(vc, text="Voice", font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").pack(fill="x")
        self.voice_var = ctk.StringVar(value=list(VOICES.keys())[0])
        ctk.CTkOptionMenu(vc, values=list(VOICES.keys()), variable=self.voice_var,
                          height=36, font=ctk.CTkFont(size=12)).pack(fill="x", pady=(4, 0))

        tc = ctk.CTkFrame(row, fg_color="transparent")
        tc.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(tc, text="Voiceover", font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").pack(fill="x")
        self.voiceover_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(tc, text="On", variable=self.voiceover_var,
                      onvalue=True, offvalue=False).pack(anchor="w", pady=(8, 0))

        ctk.CTkButton(f, text="Generate Reel", height=40,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self.generate).pack(fill="x", pady=(6, 4))
        ctk.CTkLabel(f, text="Takes 2–4 minutes. Progress shown in the main window.",
                     font=ctk.CTkFont(size=11), text_color="gray").pack()

    def generate(self):
        topic     = self.topic_entry.get().strip()
        script    = self.textbox.get("0.0", "end").strip()
        voiceover = self.voiceover_var.get()
        voice     = VOICES[self.voice_var.get()]

        if not topic:
            messagebox.showwarning("Missing", "Please enter a topic.")
            return
        if voiceover and not script:
            messagebox.showwarning("Missing", "Please enter a script or turn voiceover off.")
            return

        self.destroy()
        self.parent.start_script_to_video(topic, script, voiceover, voice)


# ---------------------------------------------------------------------------
# Script to AI Video
# ---------------------------------------------------------------------------

class ScriptToAIVideoDialog(ctk.CTkToplevel):
    def __init__(self, parent, prefill_topic="", prefill_script=""):
        super().__init__(parent)
        self.parent = parent
        self._prefill_topic  = prefill_topic
        self._prefill_script = prefill_script
        self.title("Script to AI Video")
        self.geometry("600x620")
        self.resizable(False, False)
        self._build_ui()

    def _build_ui(self):
        ctk.CTkButton(self, text="← Back", width=70, height=26,
                      fg_color="transparent", hover_color="#2a2a2a",
                      font=ctk.CTkFont(size=12), text_color="gray",
                      anchor="w", command=self.destroy
                      ).pack(anchor="w", padx=16, pady=(12, 0))

        ctk.CTkLabel(self, text="Script to AI Video",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(6, 2))
        ctk.CTkLabel(self, text="Generates real video clips with Hailuo AI via Replicate.",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 16))

        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="x", padx=30)

        ctk.CTkLabel(f, text="Topic", font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").pack(fill="x")
        self.topic_entry = ctk.CTkEntry(f, height=36,
                                        placeholder_text='e.g. Spider-Man Marvel action',
                                        font=ctk.CTkFont(size=13))
        self.topic_entry.pack(fill="x", pady=(4, 12))
        if self._prefill_topic:
            self.topic_entry.insert(0, self._prefill_topic)

        ctk.CTkLabel(f, text="Script", font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").pack(fill="x")
        self.textbox = ctk.CTkTextbox(f, height=120, font=ctk.CTkFont(size=13))
        self.textbox.pack(fill="x", pady=(4, 12))
        default = self._prefill_script or "Spider-Man has defeated Thanos not once, but THREE times in the comics."
        self.textbox.insert("0.0", default)

        ctk.CTkLabel(f, text="Voice", font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").pack(fill="x")
        self.voice_var = ctk.StringVar(value=list(VOICES.keys())[0])
        ctk.CTkOptionMenu(f, values=list(VOICES.keys()), variable=self.voice_var,
                          height=36, font=ctk.CTkFont(size=12)).pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(f, text="Replicate API Token",
                     font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x")
        self.api_token_entry = ctk.CTkEntry(
            f, height=36, show="*",
            placeholder_text="r8_xxxx  —  replicate.com → Account → API Tokens",
            font=ctk.CTkFont(size=13))
        self.api_token_entry.pack(fill="x", pady=(4, 16))

        ctk.CTkButton(f, text="Generate AI Reel", height=40,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self.generate).pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(f, text="Takes 5–15 minutes. Progress shown in the main window.",
                     font=ctk.CTkFont(size=11), text_color="gray").pack()

    def generate(self):
        topic     = self.topic_entry.get().strip()
        script    = self.textbox.get("0.0", "end").strip()
        voice     = VOICES[self.voice_var.get()]
        api_token = self.api_token_entry.get().strip()

        if not topic:
            messagebox.showwarning("Missing", "Please enter a topic.")
            return
        if not script:
            messagebox.showwarning("Missing", "Please enter a script.")
            return
        if not api_token:
            messagebox.showwarning("Missing",
                                   "Please enter your Replicate API token.\n"
                                   "Get it at: replicate.com → Account → API Tokens")
            return

        self.destroy()
        self.parent.start_script_to_ai_video(topic, script, voice, api_token)


# ---------------------------------------------------------------------------
# Comics News
# ---------------------------------------------------------------------------

class ComicsNewsDialog(ctk.CTkToplevel):
    CATEGORIES = ["All", "Marvel", "DC", "Anime", "Manhwa"]

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Comics & Anime News")
        self.geometry("820x680")
        self.resizable(True, True)
        self._build_ui()
        self._fetch("All", "", force_refresh=False)

    def _build_ui(self):
        ctk.CTkButton(self, text="← Back", width=70, height=26,
                      fg_color="transparent", hover_color="#2a2a2a",
                      font=ctk.CTkFont(size=12), text_color="gray",
                      anchor="w", command=self.destroy
                      ).pack(anchor="w", padx=16, pady=(12, 0))

        ctk.CTkLabel(self, text="Comics & Anime News",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(6, 2))
        ctk.CTkLabel(self, text="Sorted by what's trending. Updated daily.",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 12))

        # Controls
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.pack(fill="x", padx=20, pady=(0, 6))

        self.category_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(ctrl, values=self.CATEGORIES, variable=self.category_var,
                          width=110, height=34, font=ctk.CTkFont(size=13),
                          command=lambda _: self._on_search()
                          ).pack(side="left", padx=(0, 8))

        self.search_entry = ctk.CTkEntry(ctrl, height=34,
                                         placeholder_text="Search: One Piece, Batman, Solo Leveling...",
                                         font=ctk.CTkFont(size=13))
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.search_entry.bind("<Return>", lambda _: self._on_search())

        self.search_btn = ctk.CTkButton(ctrl, text="Search", width=80, height=34,
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        command=self._on_search)
        self.search_btn.pack(side="left", padx=(0, 6))

        self.refresh_btn = ctk.CTkButton(ctrl, text="Refresh", width=72, height=34,
                                         font=ctk.CTkFont(size=12),
                                         fg_color="transparent", border_width=1,
                                         command=self._force_refresh)
        self.refresh_btn.pack(side="left")

        self.news_status = ctk.CTkLabel(self, text="Loading...",
                                        font=ctk.CTkFont(size=11), text_color="gray", anchor="w")
        self.news_status.pack(anchor="w", padx=22, pady=(2, 4))

        self.scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)

    def _on_search(self):
        self._fetch(self.category_var.get(), self.search_entry.get().strip(), force_refresh=False)

    def _force_refresh(self):
        self._fetch(self.category_var.get(), self.search_entry.get().strip(), force_refresh=True)

    def _fetch(self, category, query, force_refresh=False):
        self.search_btn.configure(state="disabled", text="Loading...")
        self.refresh_btn.configure(state="disabled")
        self.news_status.configure(text="Fetching news...")
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        threading.Thread(target=self._fetch_thread,
                         args=(category, query, force_refresh), daemon=True).start()

    def _fetch_thread(self, category, query, force_refresh):
        try:
            from features.comics_news import fetch_news
            articles, age = fetch_news(category=category, query=query,
                                       max_results=20, force_refresh=force_refresh)
            self.after(0, lambda: self._show_articles(articles, age))
        except Exception as e:
            err = str(e)
            self.after(0, lambda msg=err: self.news_status.configure(text=f"Error: {msg}"))
            self.after(0, lambda: self.search_btn.configure(state="normal", text="Search"))
            self.after(0, lambda: self.refresh_btn.configure(state="normal"))

    def _show_articles(self, articles, age=""):
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self.search_btn.configure(state="normal", text="Search")
        self.refresh_btn.configure(state="normal")

        if not articles:
            self.news_status.configure(text="No results found.")
            return

        age_str = f"  —  updated {age}" if age else ""
        self.news_status.configure(text=f"{len(articles)} articles, sorted by trending{age_str}")

        for article in articles:
            self._make_card(article)

    def _make_card(self, article):
        card = ctk.CTkFrame(self.scroll_frame, corner_radius=8)
        card.pack(fill="x", pady=4, padx=14)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        title_row = ctk.CTkFrame(inner, fg_color="transparent")
        title_row.pack(fill="x")

        ctk.CTkLabel(title_row, text=article["title"] or "No title",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     wraplength=600, justify="left", anchor="w"
                     ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(title_row, text="Use for Reel", width=105, height=28,
                      font=ctk.CTkFont(size=11),
                      command=lambda a=article: self._use_for_reel(a)
                      ).pack(side="right", padx=(10, 0))

        meta = f"{article['source']}   •   {article['date'][:10] if article['date'] else ''}"
        ctk.CTkLabel(inner, text=meta, font=ctk.CTkFont(size=11),
                     text_color="gray", anchor="w").pack(anchor="w", pady=(3, 5))

        body = article.get("body", "")
        if body:
            if len(body) > 260:
                body = body[:257] + "..."
            ctk.CTkLabel(inner, text=body, font=ctk.CTkFont(size=12),
                         text_color="#aaaaaa", wraplength=740,
                         justify="left", anchor="w").pack(anchor="w")

    def _use_for_reel(self, article):
        title  = article.get("title", "")
        body   = article.get("body", "")
        topic  = title[:60]
        script = (title + ". " + body)[:400]

        picker = ctk.CTkToplevel(self)
        picker.title("Choose Type")
        picker.geometry("360x180")
        picker.resizable(False, False)
        picker.grab_set()

        ctk.CTkLabel(picker, text="Create a Reel from this article",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(24, 6))
        ctk.CTkLabel(picker, text="How do you want the video to look?",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 16))

        row = ctk.CTkFrame(picker, fg_color="transparent")
        row.pack()

        def go_slideshow():
            picker.destroy()
            self.grab_release()
            self.destroy()
            ScriptToVideoDialog(self.master, prefill_topic=topic, prefill_script=script).grab_set()

        def go_ai():
            picker.destroy()
            self.grab_release()
            self.destroy()
            ScriptToAIVideoDialog(self.master, prefill_topic=topic, prefill_script=script).grab_set()

        ctk.CTkButton(row, text="Image Slideshow", width=155, height=38,
                      command=go_slideshow).pack(side="left", padx=6)
        ctk.CTkButton(row, text="AI Video", width=155, height=38,
                      command=go_ai).pack(side="left", padx=6)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    AIVideoEditor().mainloop()
