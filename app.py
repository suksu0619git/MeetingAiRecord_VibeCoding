import customtkinter as ctk
import assemblyai as aai
import google.generativeai as genai
from tkinter import filedialog, messagebox
import threading
import soundcard as sc
import soundfile as sf
import numpy as np
import os

# ==========================================
# 1. API 키 설정 (본인의 키로 꼭 변경해주세요!)
# ==========================================
aai.settings.api_key = "settingapikey"
genai.configure(api_key="apikey")

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class MeetingApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🎙️ AI 실시간 회의록 (마이크+시스템) & 파일 요약기")
        self.geometry("650x750")
        
        self.is_recording = False
        self.audio_data = []
        self.sample_rate = 44100
        self.temp_file = "temp_meeting_record.wav"
        
        # UI 요소 배치
        self.lbl_title = ctk.CTkLabel(self, text="무엇으로 회의록을 만들까요?", font=("Arial", 16, "bold"))
        self.lbl_title.pack(pady=10)
        
        # 버튼 1: 기존의 파일 업로드 기능
        self.btn_select = ctk.CTkButton(
            self, text="📁 기존 음성 파일 찾아보기", 
            command=self.select_file, height=35
        )
        self.btn_select.pack(pady=5)
        
        # 버튼 2: 내 마이크 + 시스템 소리 동시 녹음 기능
        self.btn_record = ctk.CTkButton(
            self, text="⏺️ 내 목소리 + 컴퓨터 소리 실시간 녹음", 
            command=self.toggle_recording, 
            font=("Arial", 14, "bold"), height=40, fg_color="#E64A19", hover_color="#D84315"
        )
        self.btn_record.pack(pady=15)
        
        self.lbl_status = ctk.CTkLabel(self, text="준비 완료 (버튼을 선택해주세요)")
        self.lbl_status.pack(pady=5)
        
        # 탭(Tab) 화면 만들기
        self.tabview = ctk.CTkTabview(self, width=600, height=450)
        self.tabview.pack(pady=10)
        
        self.tabview.add("회의록 (요약)")
        self.tabview.add("대화 원본 (전체)")
        
        self.textbox_summary = ctk.CTkTextbox(self.tabview.tab("회의록 (요약)"), width=580, height=400)
        self.textbox_summary.pack(padx=10, pady=10)
        
        self.textbox_script = ctk.CTkTextbox(self.tabview.tab("대화 원본 (전체)"), width=580, height=400)
        self.textbox_script.pack(padx=10, pady=10)

    # 📁 [기능 1] 파일 선택해서 요약하기
    def select_file(self):
        if self.is_recording:
            messagebox.showwarning("경고", "녹음 중에는 파일을 올릴 수 없습니다!")
            return
            
        filepath = filedialog.askopenfilename(
            title="음성 파일 선택",
            filetypes=[("Audio Files", "*.mp3 *.wav *.m4a")]
        )
        if filepath:
            self.lbl_status.configure(text=f"선택됨: {filepath.split('/')[-1]} (분석 준비 중...)")
            self.disable_buttons()
            # 파일 분석 시작 (백그라운드 스레드)
            threading.Thread(target=self.process_and_summarize, args=(filepath,), daemon=True).start()

    # 🔴 [기능 2] 녹음 시작/종료 스위치
    def toggle_recording(self):
        if not self.is_recording:
            # 녹음 시작
            self.is_recording = True
            self.btn_select.configure(state="disabled") # 파일 업로드 버튼 막기
            self.btn_record.configure(text="⏹️ 녹음 종료 및 회의록 작성", fg_color="#C62828", hover_color="#B71C1C")
            self.lbl_status.configure(text="상태: 🔴 내 목소리와 시스템 소리를 함께 녹음 중...")
            self.audio_data = [] 
            
            threading.Thread(target=self.record_system_and_mic, daemon=True).start()
        else:
            # 녹음 종료
            self.is_recording = False
            self.disable_buttons()

    # 🎧 [기능 3] 내 목소리(마이크) + 컴퓨터 스피커 소리 합쳐서 녹음하기
    def record_system_and_mic(self):
        try:
            speaker = sc.default_speaker()
            # 1. 루프백(시스템)과 마이크 장치 설정
            loopback_mic = sc.get_microphone(id=speaker.id, include_loopback=True)
            default_mic = sc.default_microphone()
            
            chunk_size = int(self.sample_rate * 0.1)
            
            # 녹음 시작 전 상태 업데이트
            print(f"시스템 장치: {loopback_mic.name}")
            print(f"마이크 장치: {default_mic.name}")

            with loopback_mic.recorder(samplerate=self.sample_rate) as l_mic, \
                 default_mic.recorder(samplerate=self.sample_rate) as d_mic:
                
                while self.is_recording:
                    l_data = l_mic.record(numframes=chunk_size)
                    d_data = d_mic.record(numframes=chunk_size)
    
    # 1. 마이크 소리가 1채널(모노)일 경우를 대비해 2채널(스테레오)로 강제 복사
    # (l_data는 시스템 소리라 보통 2채널이지만, 혹시 모르니 둘 다 체크합니다)
                    if d_data.shape[1] == 1:
                        d_data = np.tile(d_data, (1, 2))
                    if l_data.shape[1] == 1:
                        l_data = np.tile(l_data, (1, 2))

    # 2. 믹싱 밸런스 조정 (시스템 소리가 너무 크면 목소리가 묻힙니다)
    # 시스템 소리는 40%로 줄이고, 내 목소리는 100% 그대로 혹은 더 키워서 합칩니다.
                    mixed_data = (l_data * 0.4) + (d_data * 1.5)
    
    # 3. 소리가 깨지지 않도록 한계치 설정 후 저장
                    mixed_data = np.clip(mixed_data, -1.0, 1.0)
                    self.audio_data.append(mixed_data)
            
            if len(self.audio_data) > 0:
                self.lbl_status.configure(text="상태: ⏳ 임시 오디오 파일로 저장 중...")
                audio_np = np.concatenate(self.audio_data, axis=0)
                # 데이터 타입 확인 및 저장
                sf.write(self.temp_file, audio_np, self.sample_rate)
                
                # 분석 함수로 파일 넘기기
                self.process_and_summarize(self.temp_file)
                
        except Exception as e:
            self.is_recording = False
            self.after(0, self.enable_buttons) # 메인 스레드 UI 업데이트 안전하게 호출
            messagebox.showerror("녹음 오류", f"마이크나 시스템 소리를 가져오는 중 오류가 발생했습니다:\n{e}")
    # ⚙️ [기능 4] 음성 인식 및 AI 요약 (공통 기능)
    def process_and_summarize(self, target_file):
        try:
            # 1. 음성 인식 및 화자 분리
            self.lbl_status.configure(text="상태: ⏳ 음성 분석 및 화자 분리 중... (최대 5분 소요)")
            config = aai.TranscriptionConfig(
                speaker_labels=True,
                language_code="ko",
                speech_models=["universal-2"] 
            )
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe(target_file, config)
            
            if getattr(transcript, 'error', None):
                raise Exception(f"음성 인식 오류: {transcript.error}")
            
            script = ""
            if getattr(transcript, 'utterances', None):
                for utterance in transcript.utterances:
                    script += f"참석자 {utterance.speaker}: {utterance.text}\n\n"
            else:
                script = getattr(transcript, 'text', "음성을 변환하지 못했습니다.")
            
            # 2. 회의록 요약
            self.lbl_status.configure(text="상태: ⏳ 대화 내용을 바탕으로 회의록 요약 중...")
            model = genai.GenerativeModel('gemini-3-flash-preview')
            prompt = f"""
            다음 대화 내용을 읽고, 아래의 양식에 맞춰서 회의록을 작성해줘.
            [회의록 양식]
            - 회의 내용:
            - 회의 결과:
            - 기타 안건:
            
            [대화 내용]
            {script}
            """
            response = model.generate_content(prompt)
            
            # 3. 결과 출력
            self.lbl_status.configure(text="상태: ✅ 작업 완료!")
            self.textbox_summary.delete("0.0", "end")
            self.textbox_summary.insert("0.0", response.text)
            self.textbox_script.delete("0.0", "end")
            self.textbox_script.insert("0.0", script)
            
            # 녹음으로 만들어진 임시 파일이면 삭제해서 컴퓨터 용량 확보
            if target_file == self.temp_file and os.path.exists(self.temp_file):
                os.remove(self.temp_file)
                
        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["quota", "limit", "429", "payment"]):
                messagebox.showwarning("무료 제공량 초과", "이번 달 무료 API 제공량을 모두 사용한 것 같습니다!")
            else:
                messagebox.showerror("오류 발생", f"작업 중 오류가 발생했습니다:\n{e}")
            self.lbl_status.configure(text="상태: ❌ 작업 중단 (오류 발생)")
            
        finally:
            self.enable_buttons()

    # 버튼들 비활성화 (작업 도중 중복 클릭 방지)
    def disable_buttons(self):
        self.btn_select.configure(state="disabled")
        self.btn_record.configure(state="disabled", text="처리 중... (기다려주세요)")

    # 버튼들 활성화 (작업 완료 후 원상복구)
    def enable_buttons(self):
        self.btn_select.configure(state="normal")
        self.btn_record.configure(state="normal", text="⏺️ 내 목소리 + 컴퓨터 소리 실시간 녹음", fg_color="#E64A19", hover_color="#D84315")

if __name__ == "__main__":
    app = MeetingApp()
    app.mainloop()