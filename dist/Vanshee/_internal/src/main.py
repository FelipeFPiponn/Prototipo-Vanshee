import sys
from src.routines.db import init_db
from src.audio.recorder import AudioRecorder
from src.audio.stt_whisper import WhisperSTT
from src.audio.tts_engine import TTSEngine
from src.brain import VansheeBrain

def main():
    print("=== V.ANSHEE Core [Sistema de Control por Voz] ===")
    init_db()
    
    tts = TTSEngine()
    recorder = AudioRecorder()
    stt = WhisperSTT()
    brain = VansheeBrain(tts=tts)

    ready_msg = "Sistema V.ANSHEE listo y escuchando intenciones."
    print(f"\n[V.ANSHEE] {ready_msg}")
    tts.speak("Sistema V.ANSHEE listo.", block=False)

    while True:
        try:
            print("\n----------------------------------------------")
            input("Presiona [ENTER] para hablar...")
            
            audio_file = recorder.record()
            transcription = stt.transcribe(audio_file)
            print(f"[Transcripción STT]: '{transcription}'")

            if not transcription.strip():
                msg = "No detecté ninguna instrucción clara."
                print(f"[V.ANSHEE] {msg}")
                tts.speak(msg)
                continue

            result = brain.handle_user_input(transcription)

            if result.success:
                print("\n[V.ANSHEE] Instrucción ejecutada correctamente.")
            else:
                print("\n[V.ANSHEE] La instrucción no pudo completarse con éxito.")

        except KeyboardInterrupt:
            shutdown_msg = "Apagando el núcleo de V.ANSHEE."
            print(f"\n[V.ANSHEE] {shutdown_msg}")
            tts.speak(shutdown_msg)
            sys.exit(0)
        except Exception as e:
            print(f"\n[V.ANSHEE Error inesperado]: {e}")

if __name__ == "__main__":
    main()
