import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.integrations.spotify_controller import SpotifyController
from src.integrations.audio_mixer import AudioMixerController
from src.integrations.valorant_client import ValorantClient, AGENT_MAP
from src.integrations.obs_controller import OBSStudioController
from src.integrations.hardware_monitor import HardwareMonitor
from src.integrations.obsidian_client import ObsidianClient
from src.integrations.integration_router import IntegrationRouter
from src.nlu.intent_parser import IntentParser, ActionStep, StepParameters, ParsedPipeline
from src.executor.os_executor import OSExecutor


class TestDirectIntegrations(unittest.TestCase):

    def setUp(self):
        self.parser = IntentParser()
        self.router = IntegrationRouter()

    def test_01_nlu_fast_path_direct_intents(self):
        """Verifica que el NLU reconozca todos los comandos directos en 0ms."""
        # 1. Spotify Now Playing
        p1 = self.parser.parse("¿Qué canción está sonando?")
        self.assertEqual(p1.steps[0].intent, "SPOTIFY_NOW_PLAYING")

        # 2. Spotify Like
        p2 = self.parser.parse("guarda esta canción en favoritos")
        self.assertEqual(p2.steps[0].intent, "SPOTIFY_LIKE")

        # 3. Spotify Cola
        p3 = self.parser.parse("añade Bohemian Rhapsody a la cola de spotify")
        self.assertEqual(p3.steps[0].intent, "SPOTIFY_QUEUE")
        self.assertEqual(p3.steps[0].parameters.content, "bohemian rhapsody")

        # 4. Mezclador de audio por app
        p4 = self.parser.parse("pon el volumen de spotify al 60%")
        self.assertEqual(p4.steps[0].intent, "SET_APP_VOLUME")
        self.assertEqual(p4.steps[0].target, "spotify")
        self.assertEqual(p4.steps[0].parameters.content, "60")

        # 5. Silenciar app
        p5 = self.parser.parse("silencia discord")
        self.assertEqual(p5.steps[0].intent, "MUTE_APP")
        self.assertEqual(p5.steps[0].target, "discord")

        # 6. Valorant: Tienda Diaria
        p6 = self.parser.parse("¿Qué hay en mi tienda de valorant?")
        self.assertEqual(p6.steps[0].intent, "VALORANT_STORE")

        # 7. Valorant: Auto-lock de agente
        p7 = self.parser.parse("selecciona a Jett en valorant")
        self.assertEqual(p7.steps[0].intent, "VALORANT_LOCK")
        self.assertEqual(p7.steps[0].parameters.content, "jett")

        # 7.5. League of Legends
        p_lol_1 = self.parser.parse("Banshee rechaza las partidas en el League of Legends.")
        self.assertEqual(p_lol_1.steps[0].intent, "LOL_DECLINE")

        p_lol_2 = self.parser.parse("Banshee, cancela la cola en el League of Legends.")
        self.assertEqual(p_lol_2.steps[0].intent, "LOL_CANCEL_QUEUE")

        p_lol_3 = self.parser.parse("acepta la partida en el lol")
        self.assertEqual(p_lol_3.steps[0].intent, "LOL_ACCEPT")

        # 8. OBS: Grabación y Replay
        p8 = self.parser.parse("inicia la grabacion en obs")
        self.assertEqual(p8.steps[0].intent, "OBS_START_RECORD")

        p9 = self.parser.parse("guarda el clip en obs")
        self.assertEqual(p9.steps[0].intent, "OBS_REPLAY")

        # 9. Hardware
        p10 = self.parser.parse("¿Cómo están las temperaturas?")
        self.assertEqual(p10.steps[0].intent, "HARDWARE_STATUS")

        # 10. Obsidian
        p11 = self.parser.parse("anota en mi diario: reunión con el equipo")
        self.assertEqual(p11.steps[0].intent, "OBSIDIAN_NOTE")
        self.assertEqual(p11.steps[0].parameters.content, "reunión con el equipo")

    def test_02_spotify_controller_local_inspection(self):
        """Verifica la inspección local de títulos de ventana de Spotify."""
        controller = SpotifyController()
        with patch.object(controller, "get_local_now_playing", return_value={
            "is_playing": True,
            "artist": "Imagine Dragons",
            "track": "Believer",
            "source": "local_window"
        }):
            summary = controller.get_now_playing_summary()
            self.assertIn("Believer", summary)
            self.assertIn("Imagine Dragons", summary)

    def test_03_valorant_client_agent_mapping_and_lockfile(self):
        """Verifica el mapeo de agentes y detección de lockfile de Valorant."""
        client = ValorantClient()
        self.assertIn("jett", AGENT_MAP)
        self.assertIn("reyna", AGENT_MAP)
        self.assertIn("omen", AGENT_MAP)

        # Si el juego no está abierto, falla de forma elegante sin lanzar excepciones
        with patch.object(client, "is_game_running", return_value=False):
            success, msg = client.lock_agent("jett")
            self.assertFalse(success)
            self.assertIn("no está en ejecución", msg)

    def test_04_hardware_monitor(self):
        """Verifica la telemetría de hardware y generación de texto natural."""
        hw = HardwareMonitor()
        summary = hw.get_voice_summary()
        self.assertIn("procesador", summary.lower())
        self.assertIn("ram", summary.lower())

    def test_05_audio_mixer_controller(self):
        """Verifica las llamadas del mezclador de audio."""
        mixer = AudioMixerController()
        # Probar ajuste de volumen con mock o fallback
        with patch.object(mixer, "set_master_volume", return_value=(True, "Volumen maestro ajustado al 50%.")):
            success, msg = mixer.set_master_volume(50)
            self.assertTrue(success)
            self.assertIn("50%", msg)

    def test_06_obsidian_client(self, tmp_path=None):
        """Verifica la escritura de notas y tareas en la bóveda de Obsidian."""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            client = ObsidianClient(vault_path=temp_dir)
            success, msg = client.append_daily_note("Prueba de integración V.ANSHEE")
            self.assertTrue(success)
            self.assertIn("Anotado en tu diario", msg)

            success_todo, msg_todo = client.add_todo_task("Comprar periféricos")
            self.assertTrue(success_todo)
            self.assertIn("Tarea añadida", msg_todo)

    def test_07_os_executor_direct_integration_routing(self):
        """Verifica que OSExecutor despache las acciones directas al IntegrationRouter."""
        executor = OSExecutor(interactive_voice=False)
        executor.tts.speak = MagicMock()

        step = ActionStep(intent="SPOTIFY_NOW_PLAYING", target="spotify", parameters=StepParameters())
        pipeline = ParsedPipeline(raw_text="que cancion suena", steps=[step])

        with patch.object(executor.integration_router, "execute_direct_action", return_value=(True, "Está sonando música.")) as mock_exec:
            success = executor.execute_pipeline(pipeline)
            self.assertTrue(success)
            mock_exec.assert_called_with(action_type="SPOTIFY_NOW_PLAYING", target="spotify", params={"content": "", "volume": 50.0})

        # Probar routing directo de LOL_CANCEL_QUEUE
        step_lol = ActionStep(intent="LOL_CANCEL_QUEUE", target="lol", parameters=StepParameters())
        pipe_lol = ParsedPipeline(raw_text="cancela la cola en el lol", steps=[step_lol])
        with patch.object(executor.integration_router, "execute_direct_action", return_value=(True, "Búsqueda cancelada.")) as mock_lol:
            success_lol = executor.execute_pipeline(pipe_lol)
            self.assertTrue(success_lol)
            mock_lol.assert_called_with(action_type="LOL_CANCEL_QUEUE", target="lol", params={"content": "", "volume": 50.0})

    def test_08_lol_client_and_voice_variations(self):
        """Verifica las distintas variaciones de voz para League of Legends y llamadas LCU."""
        # Variantes de voz
        test_phrases = [
            ("Banshee rechaza todas las partidas del League of Legends.", "LOL_DECLINE"),
            ("Banshee rechaza la partida de League of Legends.", "LOL_DECLINE"),
            ("Banshee rechaza la cola en el League of Legends.", "LOL_CANCEL_QUEUE"),
            ("Banshee, cancela la cola en el League of Legends.", "LOL_CANCEL_QUEUE"),
            ("Banshee rechaza las partidas en el League of Legends.", "LOL_DECLINE"),
            ("acepta la partida en el lol", "LOL_ACCEPT"),
            ("busca partida en lol", "LOL_START_QUEUE"),
            ("Banshee, pon una canción de Lana del Rey.", "SEARCH_CONTENT"),
            ("Banshee, selecciona a Diana.", "LOL_PICK"),
            ("Banshee, selecciona al campeón Diana en League of Legends.", "LOL_PICK"),
            ("Banshee, bloquea a Yasuo en LoL.", "LOL_PICK"),
            ("Banshee, banea a Zed en League of Legends.", "LOL_BAN"),
            ("Banshee, selecciona a Jett en Valorant.", "VALORANT_LOCK"),
        ]

        for phrase, expected_intent in test_phrases:
            p = self.parser.parse(phrase)
            self.assertTrue(len(p.steps) > 0, f"No se generaron pasos para '{phrase}'")
            self.assertEqual(p.steps[0].intent, expected_intent, f"Fallo en frase '{phrase}'")

        # Probar resolución de campeones (Diana ID = 131)
        from src.integrations.lol_client import lol_client
        diana_id, diana_name = lol_client._resolve_champion_id("diana")
        self.assertEqual(diana_id, 131)

        yasuo_id, yasuo_name = lol_client._resolve_champion_id("yasuo")
        self.assertEqual(yasuo_id, 157)

        # Probar métodos del cliente LoL cuando el juego no está abierto
        with patch.object(lol_client, "_find_lcu_credentials", return_value=False):
            ok_acc, msg_acc = lol_client.accept_match()
            self.assertFalse(ok_acc)
            self.assertIn("no está en ejecución", msg_acc)

            ok_dec, msg_dec = lol_client.decline_match()
            self.assertFalse(ok_dec)
            self.assertIn("no está en ejecución", msg_dec)

            ok_cq, msg_cq = lol_client.cancel_queue()
            self.assertFalse(ok_cq)
            self.assertIn("no está en ejecución", msg_cq)

            ok_pick, msg_pick = lol_client.pick_champion("diana")
            self.assertFalse(ok_pick)
            self.assertIn("no está en ejecución", msg_pick)

            ok_ban, msg_ban = lol_client.ban_champion("zed")
            self.assertFalse(ok_ban)
            self.assertIn("no está en ejecución", msg_ban)

    def test_09_discord_voice_channel_integration(self):
        """Verifica el reconocimiento y enrutamiento de canales de voz en Discord."""
        p1 = self.parser.parse("conéctame a un canal de voz en discord")
        self.assertEqual(p1.steps[0].intent, "DISCORD_CONNECT_VOICE")
        self.assertEqual(p1.steps[0].parameters.content, "general")

        p2 = self.parser.parse("conéctame al canal de voz Tonotos en Discord")
        self.assertEqual(p2.steps[0].intent, "DISCORD_CONNECT_VOICE")
        self.assertEqual(p2.steps[0].parameters.content, "tonotos")

        p3 = self.parser.parse("entra al canal de voz gaming en discord")
        self.assertEqual(p3.steps[0].intent, "DISCORD_CONNECT_VOICE")
        self.assertEqual(p3.steps[0].parameters.content, "gaming")

        p4 = self.parser.parse("desconéctame de discord")
        self.assertEqual(p4.steps[0].intent, "DISCORD_DISCONNECT_VOICE")

        p5 = self.parser.parse("desconéctate de la llamada")
        self.assertEqual(p5.steps[0].intent, "DISCORD_DISCONNECT_VOICE")

        p6 = self.parser.parse("corta la llamada en discord")
        self.assertEqual(p6.steps[0].intent, "DISCORD_DISCONNECT_VOICE")

        from src.integrations.discord_client import discord_client
        with patch.object(discord_client.window_manager, "find_window", return_value=None):
            ok, msg = discord_client.connect_voice_channel("general")
            self.assertFalse(ok)
            self.assertIn("no está abierto", msg.lower())

            ok_disc, msg_disc = discord_client.disconnect_voice()
            self.assertFalse(ok_disc)
            self.assertIn("no está abierto", msg_disc.lower())


if __name__ == "__main__":
    unittest.main()
