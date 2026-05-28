import signal
import unittest
from unittest.mock import patch

import run_pet_agent


class RunPetAgentTest(unittest.TestCase):
    @patch("run_pet_agent.os.getpgid")
    @patch("run_pet_agent.os.getpid")
    @patch("run_pet_agent.subprocess.check_output")
    def test_matching_process_groups_ignores_current_group(
        self,
        check_output,
        getpid,
        getpgid,
    ):
        getpid.return_value = 100
        getpgid.return_value = 100
        check_output.return_value = "\n".join(
            [
                "100 100 python run_pet_agent.py",
                "101 100 python telegram_bot.py",
                "202 202 python telegram_bot.py",
                "303 303 rg telegram_bot.py",
            ]
        )

        groups = run_pet_agent._matching_process_groups("telegram_bot.py")

        self.assertEqual({202: [202]}, groups)

    @patch("run_pet_agent.time.sleep")
    @patch("run_pet_agent.time.monotonic", side_effect=[0, 6])
    @patch("run_pet_agent.os.killpg")
    @patch("run_pet_agent._matching_process_groups")
    def test_stop_existing_process_groups_terminates_matches(
        self,
        matching_process_groups,
        killpg,
        _monotonic,
        _sleep,
    ):
        matching_process_groups.side_effect = [{202: [202]}, {}]

        run_pet_agent._stop_existing_process_groups("telegram", "telegram_bot.py")

        killpg.assert_called_once_with(202, signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
