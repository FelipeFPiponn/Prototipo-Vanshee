import sys
from src.audio.audio_recorder import AudioRecorder
from src.audio.stt_whisper import WhisperSTT
from src.nlu.intent_parser import IntentParser
from src.executor.os_executor import OSExecutor

def main():
    print("=== V.ANSHEE Core [Sistema de Control por Voz] ===")
    
    recorder = AudioRecorder()
    stt = WhisperSTT()
    parser = IntentParser()
    executor = OSExecutor()

    print("\n[V.ANSHEE] Sistema iniciado y listo para recibir intenciones.")

    while True:
        try:
            input("\nPresiona [ENTER] para hablar...")
            
            audio_file = recorder.record()
            transcription = stt.transcribe(audio_file)
            print(f"[Transcripción STT]: '{transcription}'")

            if not transcription.strip():
                print("[V.ANSHEE] No se detectó ninguna instrucción clara.")
                continue

            pipeline = parser.parse(transcription)
            executor.execute(pipeline)

        except KeyboardInterrupt:
            print("\n[V.ANSHEE] Apagando el sistema...")
            sys.exit(0)

if __name__ == "__main__":
    main()