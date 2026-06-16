from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DesktopPetMacRuntimeTest(unittest.TestCase):
    def test_walk_animation_actions_force_window_movement(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertIn("let defaultWalkTicks = 32", source)
        self.assertIn("func isWalkAction(_ action: String) -> Bool", source)
        self.assertIn('return action == "walk_left" || action == "walk_right"', source)
        self.assertIn("if isWalkAction(currentAction) && actionTicks <= 0", source)
        self.assertIn("actionTicks = defaultWalkTicks", source)
        self.assertIn("} else if isWalkAction(currentAction) {", source)
        self.assertIn("stepForcedWalk(in: screen)", source)
        self.assertIn("func stepForcedWalk(in screen: NSRect)", source)
        self.assertIn("wanderTarget = nil", source)
        self.assertIn("wanderPauseTicks = 0", source)
        self.assertIn('dx = currentAction == "walk_right" ? 1 : -1', source)
        self.assertIn("let speed = directionalWalkSpeed(forcedWalkSpeed, dx: dx)", source)
        self.assertIn("frame.origin.x += dx * speed", source)
        self.assertIn("window.setFrame(frame, display: true)", source)

    def test_leisure_walk_stops_in_idle_animation(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertRegex(
            source,
            re.compile(r"if wanderPauseTicks > 0 \{.*?currentAction = \"idle\".*?return", re.S),
        )
        self.assertRegex(
            source,
            re.compile(r"guard let target = wanderTarget else \{.*?currentAction = \"idle\".*?return", re.S),
        )
        self.assertNotIn('currentAction = "relax"', source)

    def test_walk_speeds_are_not_slow_motion(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")
        forced_speed = re.search(r"let forcedWalkSpeed: CGFloat = ([0-9.]+)", source)
        leisure_speed = re.search(r"let leisureWalkSpeed: CGFloat = ([0-9.]+)", source)
        right_multiplier = re.search(r"let rightWalkSpeedMultiplier: CGFloat = ([0-9.]+)", source)

        self.assertIsNotNone(forced_speed)
        self.assertIsNotNone(leisure_speed)
        self.assertIsNotNone(right_multiplier)
        self.assertGreaterEqual(float(forced_speed.group(1)), 1.4)
        self.assertGreaterEqual(float(leisure_speed.group(1)), 1.3)
        self.assertGreaterEqual(float(right_multiplier.group(1)), 1.2)

    def test_right_walk_uses_directional_speed_multiplier(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertIn("func directionalWalkSpeed(_ baseSpeed: CGFloat, dx direction: CGFloat) -> CGFloat", source)
        self.assertIn("return direction > 0 ? baseSpeed * rightWalkSpeedMultiplier : baseSpeed", source)
        self.assertIn("let speed = directionalWalkSpeed(forcedWalkSpeed, dx: dx)", source)
        self.assertIn("frame.origin.x += dx * speed", source)
        self.assertIn("let speed = directionalWalkSpeed(leisureWalkSpeed, dx: deltaX)", source)
        self.assertIn("speed = directionalWalkSpeed(speed, dx: deltaX)", source)

    def test_leisure_wander_plays_walk_without_persisting_walk_state(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertIn('let walkAction = deltaX >= 0 ? "walk_right" : "walk_left"', source)
        self.assertIn("petView.tick(action: walkAction)", source)
        self.assertNotIn('currentAction = deltaX >= 0 ? "walk_right" : "walk_left"', source)

    def test_leisure_wander_ignores_targets_that_are_too_close(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertIn("let minimumLeisureWalkDistance: CGFloat = 120", source)
        self.assertIn("pointDistance(frame.origin, waypoint) >= wanderArrivalDistance", source)
        self.assertIn("let safeDistance = max(1, distance)", source)
        self.assertIn("hypot(candidateOrigin.x - currentFrame.origin.x, candidateOrigin.y - currentFrame.origin.y) < minimumLeisureWalkDistance", source)
        self.assertIn("return nil", source)

    def test_random_wander_targets_exclude_current_pet_frame(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertIn("func chooseWanderTarget(in screen: NSRect, currentFrame: NSRect) -> NSPoint?", source)
        self.assertIn("func isValidWanderTarget(_ candidateOrigin: NSPoint, currentFrame: NSRect, occupied: [NSRect]) -> Bool", source)
        self.assertIn("let currentTargetExclusion = currentFrame.insetBy(dx: -24, dy: -16)", source)
        self.assertIn("if currentTargetExclusion.contains(candidateOrigin) { return false }", source)
        self.assertIn("if candidateFrame.intersects(currentTargetExclusion) { return false }", source)
        self.assertNotIn("return currentFrame.origin", source)

    def test_leisure_wander_does_not_tick_walk_when_clamped_in_place(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertIn("let previousOrigin = frame.origin", source)
        self.assertIn("let movedDistance = pointDistance(previousOrigin, frame.origin)", source)
        self.assertIn("if movedDistance < 0.5", source)
        self.assertRegex(
            source,
            re.compile(r"frame\.origin = clamp\(frame\.origin, for: frame\.size, in: screen\).*?if movedDistance < 0\.5.*?petView\.tick\(action: currentAction\).*?return.*?let walkAction", re.S),
        )

    def test_leisure_wander_routes_around_occupied_windows(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertIn("let windowAvoidancePadding: CGFloat = 28", source)
        self.assertIn("let avoidanceWaypointGap: CGFloat = 20", source)
        self.assertIn("var wanderWaypoint: NSPoint?", source)
        self.assertIn("wanderWaypoint = nil", source)
        self.assertIn("func nextLeisureRouteTarget(", source)
        self.assertIn("firstBlockingWindow(from: frame, to: finalTarget, occupied: occupied)", source)
        self.assertIn("avoidanceWaypoint(", source)
        self.assertIn("wanderWaypoint = waypoint", source)
        self.assertIn("guard let routeTarget = nextLeisureRouteTarget(", source)
        self.assertIn("currentAction = \"idle\"", source)

    def test_window_avoidance_detects_segment_intersections(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertIn("extension NSRect", source)
        self.assertIn("var center: NSPoint", source)
        self.assertIn("func firstBlockingWindow(from frame: NSRect, to target: NSPoint, occupied: [NSRect]) -> NSRect?", source)
        self.assertIn("segmentIntersectsRect(start, finish, expanded)", source)
        self.assertIn("func segmentIntersectsRect(_ start: NSPoint, _ end: NSPoint, _ rect: NSRect) -> Bool", source)
        self.assertIn("func segmentsIntersect(_ a: NSPoint, _ b: NSPoint, _ c: NSPoint, _ d: NSPoint) -> Bool", source)
        self.assertIn("func isFrameClear(at origin: NSPoint, size: NSSize, occupied: [NSRect]) -> Bool", source)

    def test_play_mode_only_stops_from_context_menu(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertNotIn("playFollowTicks", source)
        self.assertIn('delegate?.currentAction == "play"', source)
        self.assertIn('menu.addItem(withTitle: "停止陪玩", action: #selector(AppDelegate.stopPlayFromMenu), keyEquivalent: "")', source)
        self.assertIn('menu.addItem(withTitle: "陪玩", action: #selector(AppDelegate.playFromMenu), keyEquivalent: "")', source)
        self.assertIn('currentAction != "sleep" && currentAction != "play"', source)
        self.assertIn('currentAction != "idle" && currentAction != "sleep" && currentAction != "play" && !isWalkAction(currentAction)', source)
        self.assertRegex(
            source,
            re.compile(r"@objc func playFromMenu\(\) \{.*?currentAction = \"play\".*?actionTicks = 0", re.S),
        )
        self.assertRegex(
            source,
            re.compile(r"@objc func stopPlayFromMenu\(\) \{.*?stopLureCursor\(\).*?currentAction = \"idle\".*?actionTicks = 0", re.S),
        )

    def test_short_sleep_can_auto_wake_or_be_woken_from_menu(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertIn("let shortSleepTicks = 2500", source)
        self.assertIn('delegate?.currentAction == "sleep"', source)
        self.assertIn('menu.addItem(withTitle: "叫醒", action: #selector(AppDelegate.wakeFromMenu), keyEquivalent: "")', source)
        self.assertIn('menu.addItem(withTitle: "睡一会儿", action: #selector(AppDelegate.sleepFromMenu), keyEquivalent: "")', source)
        self.assertIn('if actionTicks == 0 && currentAction == "sleep"', source)
        self.assertIn('wakeFromSleep(speech: "睡醒啦，回到待机。")', source)
        self.assertRegex(
            source,
            re.compile(r"@objc func sleepFromMenu\(\) \{.*?currentAction = \"sleep\".*?actionTicks = shortSleepTicks", re.S),
        )
        self.assertRegex(
            source,
            re.compile(r"func wakeFromSleep\(speech text: String\) \{.*?currentAction = \"idle\".*?wanderPauseTicks = 24", re.S),
        )
        self.assertRegex(
            source,
            re.compile(r"@objc func wakeFromMenu\(\) \{.*?wakeFromSleep\(speech: \"醒啦，继续陪你。\"\)", re.S),
        )

    def test_context_menu_exposes_simple_assistant_tools(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertIn('menu.addItem(withTitle: "记事...", action: #selector(AppDelegate.noteFromMenu), keyEquivalent: "")', source)
        self.assertIn('menu.addItem(withTitle: "待办...", action: #selector(AppDelegate.todoFromMenu), keyEquivalent: "")', source)
        self.assertIn('menu.addItem(withTitle: "提醒...", action: #selector(AppDelegate.alarmFromMenu), keyEquivalent: "")', source)
        self.assertIn('menu.addItem(withTitle: "番茄钟...", action: #selector(AppDelegate.focusFromMenu), keyEquivalent: "")', source)

    def test_desktop_assistant_items_use_shared_backend_endpoint(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertIn("let apiBaseURL: String", source)
        self.assertIn("let petID: Int?", source)
        self.assertIn("let ownerID: Int?", source)
        self.assertIn('URL(string: "\(apiBaseURL)/assistant/items")', source)
        self.assertIn('"source": "desktop"', source)
        self.assertIn('payload["pet_id"] = petID', source)
        self.assertIn('payload["owner_id"] = ownerID', source)
        self.assertIn('currentAction = "work"', source)

    def test_desktop_runtime_accepts_assistant_context_arguments(self) -> None:
        source = (PROJECT_ROOT / "desktop_pet_mac.swift").read_text(encoding="utf-8")

        self.assertIn('let apiBaseURL = argumentValue("--api-base") ?? "http://127.0.0.1:8000"', source)
        self.assertIn('let petID = Int(argumentValue("--pet-id") ?? "")', source)
        self.assertIn('let ownerID = Int(argumentValue("--owner-id") ?? "")', source)
        self.assertIn("apiBaseURL: apiBaseURL", source)
        self.assertIn("petID: petID", source)
        self.assertIn("ownerID: ownerID", source)


if __name__ == "__main__":
    unittest.main()
