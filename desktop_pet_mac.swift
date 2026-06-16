import AppKit
import CoreGraphics
import Foundation

let transparentColor = NSColor(calibratedRed: 1, green: 0, blue: 1, alpha: 1)
let petSize: CGFloat = 168
let shortSleepTicks = 2500
let defaultWalkTicks = 32
let forcedWalkSpeed: CGFloat = 1.6
let leisureWalkSpeed: CGFloat = 1.45
let rightWalkSpeedMultiplier: CGFloat = 1.35
let minimumLeisureWalkDistance: CGFloat = 120
let wanderArrivalDistance: CGFloat = 8
let windowAvoidancePadding: CGFloat = 28
let avoidanceWaypointGap: CGFloat = 20

extension NSRect {
    var center: NSPoint {
        return NSPoint(x: midX, y: midY)
    }
}

final class LureView: NSView {
    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        layer?.backgroundColor = NSColor.clear.cgColor
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.clear.setFill()
        dirtyRect.fill()

        let handle = NSBezierPath()
        handle.move(to: NSPoint(x: 10, y: 8))
        handle.line(to: NSPoint(x: 28, y: 28))
        handle.lineWidth = 4
        NSColor(calibratedRed: 0.30, green: 0.18, blue: 0.09, alpha: 1).setStroke()
        handle.stroke()

        let string = NSBezierPath()
        string.move(to: NSPoint(x: 28, y: 28))
        string.curve(
            to: NSPoint(x: 34, y: 12),
            controlPoint1: NSPoint(x: 36, y: 28),
            controlPoint2: NSPoint(x: 38, y: 18)
        )
        string.lineWidth = 1.5
        NSColor(calibratedWhite: 0.16, alpha: 0.9).setStroke()
        string.stroke()

        let ribbon = NSBezierPath()
        ribbon.move(to: NSPoint(x: 33, y: 12))
        ribbon.line(to: NSPoint(x: 39, y: 17))
        ribbon.line(to: NSPoint(x: 36, y: 8))
        ribbon.close()
        NSColor(calibratedRed: 0.95, green: 0.24, blue: 0.42, alpha: 0.95).setFill()
        ribbon.fill()
    }
}

final class PetView: NSView {
    var image: NSImage?
    var imageView: NSImageView!
    var animationPaths: [String: String] = [:]
    var currentAnimation = ""
    var dragStart: NSPoint?
    var onDoubleClick: (() -> Void)?
    var onAction: ((String) -> Void)?
    var onQuit: (() -> Void)?
    var phase: CGFloat = 0
    var action: String = "idle"

    init(imagePath: String?, manifestPath: String?) {
        if let imagePath, !imagePath.isEmpty {
            self.image = NSImage(contentsOfFile: imagePath)
        }
        if let manifestPath, !manifestPath.isEmpty {
            self.animationPaths = PetView.loadAnimations(manifestPath: manifestPath)
        }
        super.init(frame: NSRect(x: 0, y: 0, width: petSize, height: petSize))
        wantsLayer = true
        layer?.backgroundColor = NSColor.clear.cgColor

        imageView = NSImageView(frame: bounds)
        imageView.imageScaling = .scaleProportionallyUpOrDown
        imageView.animates = true
        imageView.wantsLayer = true
        imageView.layer?.backgroundColor = NSColor.clear.cgColor
        addSubview(imageView)
        setAnimation("idle")
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    static func loadAnimations(manifestPath: String) -> [String: String] {
        let manifestURL = URL(fileURLWithPath: manifestPath)
        guard
            let data = try? Data(contentsOf: manifestURL),
            let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let animationRoot = root["animations"] as? [String: Any]
        else {
            return [:]
        }

        var loaded: [String: String] = [:]
        let base = manifestURL.deletingLastPathComponent()
        for (name, value) in animationRoot {
            if let item = value as? [String: Any], let src = item["src"] as? String {
                loaded[name] = base.appendingPathComponent(src).path
            }
        }
        return loaded
    }

    func setAnimation(_ name: String) {
        let resolved = animationPaths[name] != nil ? name : "idle"
        guard currentAnimation != resolved else { return }
        currentAnimation = resolved
        if let path = animationPaths[resolved], let animated = NSImage(contentsOfFile: path) {
            imageView.image = animated
            imageView.isHidden = false
            needsDisplay = true
            return
        }
        imageView.image = image
        imageView.isHidden = image == nil
        needsDisplay = true
    }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.clear.setFill()
        dirtyRect.fill()

        if !imageView.isHidden { return }
        drawShadow()

        let stroke = NSColor(calibratedRed: 0.15, green: 0.19, blue: 0.15, alpha: 1)
        let fill = NSColor(calibratedRed: 0.93, green: 0.97, blue: 0.91, alpha: 1)
        stroke.setStroke()
        fill.setFill()

        let body = NSBezierPath(ovalIn: NSRect(x: 42, y: 44, width: 84, height: 88))
        body.lineWidth = 3
        body.fill()
        body.stroke()

        let leftEar = NSBezierPath()
        leftEar.move(to: NSPoint(x: 52, y: 50))
        leftEar.line(to: NSPoint(x: 66, y: 14))
        leftEar.line(to: NSPoint(x: 82, y: 52))
        leftEar.close()
        leftEar.lineWidth = 3
        leftEar.fill()
        leftEar.stroke()

        let rightEar = NSBezierPath()
        rightEar.move(to: NSPoint(x: 86, y: 52))
        rightEar.line(to: NSPoint(x: 104, y: 14))
        rightEar.line(to: NSPoint(x: 118, y: 50))
        rightEar.close()
        rightEar.lineWidth = 3
        rightEar.fill()
        rightEar.stroke()

        stroke.setFill()
        NSBezierPath(ovalIn: NSRect(x: 68, y: 78, width: 8, height: 8)).fill()
        NSBezierPath(ovalIn: NSRect(x: 94, y: 78, width: 8, height: 8)).fill()
        NSBezierPath(ovalIn: NSRect(x: 82, y: 96, width: 7, height: 6)).fill()
    }

    func drawShadow() {
        NSGraphicsContext.saveGraphicsState()
        NSColor(calibratedWhite: 0, alpha: 0.12).setFill()
        NSBezierPath(ovalIn: NSRect(x: 42, y: 142, width: 84, height: 12)).fill()
        NSGraphicsContext.restoreGraphicsState()
    }

    func tick(action nextAction: String) {
        action = nextAction
        phase += 0.22
        let bob = sin(phase) * 5
        let animationName: String
        if action == "play" {
            animationName = "play"
        } else if action == "walk_left" {
            animationName = "walk_left"
        } else if action == "walk_right" {
            animationName = "walk_right"
        } else if action == "pet" {
            animationName = "happy"
        } else if action == "happy" {
            animationName = "happy"
        } else if action == "feed" {
            animationName = "feed"
        } else if action == "refill" {
            animationName = "refill"
        } else if action == "clean" {
            animationName = "clean"
        } else if action == "lullaby" {
            animationName = "lullaby"
        } else if action == "sleep" {
            animationName = "sleep"
        } else if action == "work" {
            animationName = "work"
        } else if action == "relax" {
            animationName = "relax"
        } else {
            animationName = "idle"
        }
        setAnimation(animationName)
        imageView.frame = bounds.offsetBy(dx: 0, dy: bob)
        needsDisplay = true
    }

    override func mouseDown(with event: NSEvent) {
        if event.clickCount >= 2 {
            onDoubleClick?()
            return
        }
        dragStart = event.locationInWindow
    }

    override func mouseDragged(with event: NSEvent) {
        guard let window, let dragStart else { return }
        let current = event.locationInWindow
        var origin = window.frame.origin
        origin.x += current.x - dragStart.x
        origin.y += current.y - dragStart.y
        window.setFrameOrigin(origin)
    }

    override func rightMouseDown(with event: NSEvent) {
        let menu = NSMenu()
        let delegate = NSApp.delegate as? AppDelegate
        menu.addItem(withTitle: "摸摸", action: #selector(AppDelegate.petFromMenu), keyEquivalent: "")
        if delegate?.currentAction == "play" {
            menu.addItem(withTitle: "停止陪玩", action: #selector(AppDelegate.stopPlayFromMenu), keyEquivalent: "")
        } else {
            menu.addItem(withTitle: "陪玩", action: #selector(AppDelegate.playFromMenu), keyEquivalent: "")
        }
        if delegate?.currentAction == "sleep" {
            menu.addItem(withTitle: "叫醒", action: #selector(AppDelegate.wakeFromMenu), keyEquivalent: "")
        } else {
            menu.addItem(withTitle: "睡一会儿", action: #selector(AppDelegate.sleepFromMenu), keyEquivalent: "")
        }
        menu.addItem(.separator())
        menu.addItem(withTitle: "记事...", action: #selector(AppDelegate.noteFromMenu), keyEquivalent: "")
        menu.addItem(withTitle: "待办...", action: #selector(AppDelegate.todoFromMenu), keyEquivalent: "")
        menu.addItem(withTitle: "提醒...", action: #selector(AppDelegate.alarmFromMenu), keyEquivalent: "")
        menu.addItem(withTitle: "番茄钟...", action: #selector(AppDelegate.focusFromMenu), keyEquivalent: "")
        menu.addItem(.separator())
        menu.addItem(withTitle: "退出桌面宠物", action: #selector(AppDelegate.quit), keyEquivalent: "")
        NSMenu.popUpContextMenu(menu, with: event, for: self)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var speech: NSTextField!
    var petView: PetView!
    var timer: Timer?
    var dx: CGFloat = -1
    var wanderTarget: NSPoint?
    var wanderWaypoint: NSPoint?
    var wanderPauseTicks = 0
    var currentAction = "idle"
    var actionTicks = 0
    var hideSpeechWorkItem: DispatchWorkItem?
    var lureWindow: NSWindow?
    let petName: String
    let imagePath: String?
    let manifestPath: String?
    let offsetIndex: Int
    let apiBaseURL: String
    let petID: Int?
    let ownerID: Int?

    init(
        petName: String,
        imagePath: String?,
        manifestPath: String?,
        offsetIndex: Int,
        apiBaseURL: String,
        petID: Int?,
        ownerID: Int?
    ) {
        self.petName = petName
        self.imagePath = imagePath
        self.manifestPath = manifestPath
        self.offsetIndex = offsetIndex
        self.apiBaseURL = apiBaseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        self.petID = petID
        self.ownerID = ownerID
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        let content = NSView(frame: NSRect(x: 0, y: 0, width: 260, height: 230))
        content.wantsLayer = true
        content.layer?.backgroundColor = NSColor.clear.cgColor

        speech = NSTextField(labelWithString: "\(petName) 到桌面上来啦。")
        speech.frame = NSRect(x: 8, y: 176, width: 244, height: 44)
        speech.alignment = .center
        speech.font = NSFont.systemFont(ofSize: 13)
        speech.textColor = NSColor(calibratedWhite: 0.12, alpha: 1)
        speech.backgroundColor = NSColor.white.withAlphaComponent(0.92)
        speech.drawsBackground = true
        speech.isBezeled = true
        speech.lineBreakMode = .byWordWrapping
        speech.maximumNumberOfLines = 2
        content.addSubview(speech)

        petView = PetView(imagePath: imagePath, manifestPath: manifestPath)
        petView.frame = NSRect(x: 46, y: 8, width: petSize, height: petSize)
        petView.onDoubleClick = { [weak self] in
            self?.performPetAction("happy", speech: "摸摸收到。")
        }
        content.addSubview(petView)

        let screenFrame = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1200, height: 800)
        let column = CGFloat(offsetIndex % 4)
        let row = CGFloat(offsetIndex / 4)
        let origin = NSPoint(
            x: screenFrame.maxX - 300 - column * 72,
            y: screenFrame.minY + 80 + row * 82
        )
        window = NSWindow(
            contentRect: NSRect(origin: origin, size: content.frame.size),
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )
        window.contentView = content
        window.isOpaque = false
        window.backgroundColor = .clear
        window.level = .floating
        window.hasShadow = false
        window.ignoresMouseEvents = false
        window.makeKeyAndOrderFront(nil)
        hideSpeech(after: 3)

        timer = Timer.scheduledTimer(withTimeInterval: 0.12, repeats: true) { [weak self] _ in
            self?.step()
        }
    }

    func step() {
        guard let screen = NSScreen.main?.visibleFrame else { return }
        if isWalkAction(currentAction) && actionTicks <= 0 {
            actionTicks = defaultWalkTicks
        }

        if actionTicks > 0 {
            actionTicks -= 1
            if actionTicks == 0 && currentAction == "sleep" {
                wakeFromSleep(speech: "睡醒啦，回到待机。")
            } else if actionTicks == 0 && currentAction != "play" {
                currentAction = "idle"
            }
        } else if currentAction != "idle" && currentAction != "sleep" && currentAction != "play" && !isWalkAction(currentAction) {
            currentAction = "idle"
        }

        if currentAction == "play" {
            stepPlayFollow(in: screen)
        } else if isWalkAction(currentAction) {
            stepForcedWalk(in: screen)
        } else if currentAction == "idle" || currentAction == "relax" {
            stepLeisureWander(in: screen)
        } else {
            petView.tick(action: currentAction)
            var frame = window.frame
            let speed: CGFloat = currentAction == "sleep" ? 0 : 0.9
            if frame.minX <= screen.minX + 10 || frame.maxX >= screen.maxX - 10 {
                dx *= -1
            }
            frame.origin.x += dx * speed
            window.setFrame(frame, display: true)
        }
    }

    func isWalkAction(_ action: String) -> Bool {
        return action == "walk_left" || action == "walk_right"
    }

    func directionalWalkSpeed(_ baseSpeed: CGFloat, dx direction: CGFloat) -> CGFloat {
        return direction > 0 ? baseSpeed * rightWalkSpeedMultiplier : baseSpeed
    }

    func stepForcedWalk(in screen: NSRect) {
        wanderTarget = nil
        wanderWaypoint = nil
        wanderPauseTicks = 0
        var frame = window.frame
        dx = currentAction == "walk_right" ? 1 : -1

        if frame.minX <= screen.minX + 10 && dx < 0 {
            dx = 1
            currentAction = "walk_right"
        } else if frame.maxX >= screen.maxX - 10 && dx > 0 {
            dx = -1
            currentAction = "walk_left"
        }

        petView.tick(action: currentAction)
        let speed = directionalWalkSpeed(forcedWalkSpeed, dx: dx)
        frame.origin.x += dx * speed
        frame.origin = clamp(frame.origin, for: frame.size, in: screen)
        window.setFrame(frame, display: true)
    }

    func stepPlayFollow(in screen: NSRect) {
        showLureCursorIfNeeded()
        let mouse = NSEvent.mouseLocation
        updateLureCursor(to: mouse)

        var frame = window.frame
        let petCenter = NSPoint(x: frame.origin.x + 130, y: frame.origin.y + 92)
        let deltaX = mouse.x - petCenter.x
        let deltaY = mouse.y - petCenter.y
        let distance = hypot(deltaX, deltaY)

        if distance < 18 {
            petView.tick(action: "play")
            return
        }

        var speed = min(CGFloat(4.2), max(CGFloat(1.2), distance / 40))
        speed = directionalWalkSpeed(speed, dx: deltaX)
        frame.origin.x += deltaX / distance * speed
        frame.origin.y += deltaY / distance * min(speed * 0.55, abs(deltaY))
        frame.origin = clamp(frame.origin, for: frame.size, in: screen)
        dx = deltaX >= 0 ? 1 : -1
        petView.tick(action: deltaX >= 0 ? "walk_right" : "walk_left")
        window.setFrame(frame, display: true)
    }

    func stepLeisureWander(in screen: NSRect) {
        var frame = window.frame
        if wanderPauseTicks > 0 {
            wanderPauseTicks -= 1
            currentAction = "idle"
            petView.tick(action: currentAction)
            return
        }

        if shouldChooseNewWanderTarget(from: frame) {
            wanderTarget = chooseWanderTarget(in: screen, currentFrame: frame)
            wanderWaypoint = nil
            if Int.random(in: 0..<5) == 0 {
                wanderPauseTicks = Int.random(in: 16...40)
            }
        }

        guard let target = wanderTarget else {
            currentAction = "idle"
            petView.tick(action: currentAction)
            return
        }

        let finalDistance = pointDistance(frame.origin, target)
        if finalDistance < wanderArrivalDistance {
            wanderTarget = nil
            wanderWaypoint = nil
            currentAction = "idle"
            wanderPauseTicks = Int.random(in: 12...36)
            petView.tick(action: currentAction)
            return
        }

        let occupied = openWindowRects(in: screen)
        guard let routeTarget = nextLeisureRouteTarget(
            from: frame,
            finalTarget: target,
            occupied: occupied,
            in: screen
        ) else {
            currentAction = "idle"
            petView.tick(action: currentAction)
            return
        }

        let deltaX = routeTarget.x - frame.origin.x
        let deltaY = routeTarget.y - frame.origin.y
        let distance = hypot(deltaX, deltaY)
        if distance < wanderArrivalDistance {
            wanderWaypoint = nil
            petView.tick(action: "idle")
            return
        }

        let speed = directionalWalkSpeed(leisureWalkSpeed, dx: deltaX)
        let safeDistance = max(1, distance)
        let previousOrigin = frame.origin
        frame.origin.x += deltaX / safeDistance * speed
        frame.origin.y += deltaY / safeDistance * min(speed * 0.35, abs(deltaY))
        frame.origin = clamp(frame.origin, for: frame.size, in: screen)
        let movedDistance = pointDistance(previousOrigin, frame.origin)
        if movedDistance < 0.5 {
            wanderTarget = nil
            wanderWaypoint = nil
            currentAction = "idle"
            wanderPauseTicks = Int.random(in: 12...36)
            petView.tick(action: currentAction)
            window.setFrame(frame, display: true)
            return
        }

        dx = deltaX >= 0 ? 1 : -1
        let walkAction = deltaX >= 0 ? "walk_right" : "walk_left"
        petView.tick(action: walkAction)
        window.setFrame(frame, display: true)
    }

    func shouldChooseNewWanderTarget(from frame: NSRect) -> Bool {
        guard let target = wanderTarget else { return true }
        if Int.random(in: 0..<460) == 0 { return true }
        return pointDistance(target, frame.origin) < wanderArrivalDistance
    }

    func nextLeisureRouteTarget(
        from frame: NSRect,
        finalTarget: NSPoint,
        occupied: [NSRect],
        in screen: NSRect
    ) -> NSPoint? {
        if let waypoint = wanderWaypoint {
            if pointDistance(frame.origin, waypoint) >= wanderArrivalDistance {
                return waypoint
            }
            wanderWaypoint = nil
        }

        guard let obstacle = firstBlockingWindow(from: frame, to: finalTarget, occupied: occupied) else {
            return finalTarget
        }

        guard
            let waypoint = avoidanceWaypoint(
                around: obstacle,
                from: frame,
                to: finalTarget,
                occupied: occupied,
                in: screen
            )
        else {
            return nil
        }
        wanderWaypoint = waypoint
        return waypoint
    }

    func chooseWanderTarget(in screen: NSRect, currentFrame: NSRect) -> NSPoint? {
        let occupied = openWindowRects(in: screen)
        for _ in 0..<36 {
            let x = CGFloat.random(in: (screen.minX + 20)...max(screen.minX + 20, screen.maxX - currentFrame.width - 20))
            let y = CGFloat.random(in: (screen.minY + 10)...max(screen.minY + 10, screen.maxY - currentFrame.height - 10))
            let candidateOrigin = NSPoint(x: x, y: y)
            if isValidWanderTarget(candidateOrigin, currentFrame: currentFrame, occupied: occupied) {
                return candidateOrigin
            }
        }

        return nil
    }

    func isValidWanderTarget(_ candidateOrigin: NSPoint, currentFrame: NSRect, occupied: [NSRect]) -> Bool {
        let currentTargetExclusion = currentFrame.insetBy(dx: -24, dy: -16)
        if currentTargetExclusion.contains(candidateOrigin) { return false }
        if hypot(candidateOrigin.x - currentFrame.origin.x, candidateOrigin.y - currentFrame.origin.y) < minimumLeisureWalkDistance {
            return false
        }

        let candidateFrame = NSRect(origin: candidateOrigin, size: currentFrame.size)
        if candidateFrame.intersects(currentTargetExclusion) { return false }

        let candidate = candidateFrame.insetBy(dx: -24, dy: -16)
        return !occupied.contains(where: { $0.intersects(candidate) })
    }

    func firstBlockingWindow(from frame: NSRect, to target: NSPoint, occupied: [NSRect]) -> NSRect? {
        let start = frame.center
        let finish = NSRect(origin: target, size: frame.size).center
        return occupied.first { obstacle in
            let expanded = obstacle.insetBy(
                dx: -(frame.width / 2 + windowAvoidancePadding),
                dy: -(frame.height / 2 + windowAvoidancePadding)
            )
            return segmentIntersectsRect(start, finish, expanded)
        }
    }

    func avoidanceWaypoint(
        around obstacle: NSRect,
        from frame: NSRect,
        to finalTarget: NSPoint,
        occupied: [NSRect],
        in screen: NSRect
    ) -> NSPoint? {
        let expanded = obstacle.insetBy(
            dx: -(frame.width / 2 + windowAvoidancePadding),
            dy: -(frame.height / 2 + windowAvoidancePadding)
        )
        let start = frame.center
        let finish = NSRect(origin: finalTarget, size: frame.size).center
        let candidateCenters = [
            NSPoint(x: expanded.minX - avoidanceWaypointGap, y: expanded.minY - avoidanceWaypointGap),
            NSPoint(x: expanded.minX - avoidanceWaypointGap, y: expanded.maxY + avoidanceWaypointGap),
            NSPoint(x: expanded.maxX + avoidanceWaypointGap, y: expanded.minY - avoidanceWaypointGap),
            NSPoint(x: expanded.maxX + avoidanceWaypointGap, y: expanded.maxY + avoidanceWaypointGap),
            NSPoint(x: expanded.midX, y: expanded.minY - avoidanceWaypointGap),
            NSPoint(x: expanded.midX, y: expanded.maxY + avoidanceWaypointGap),
            NSPoint(x: expanded.minX - avoidanceWaypointGap, y: expanded.midY),
            NSPoint(x: expanded.maxX + avoidanceWaypointGap, y: expanded.midY),
        ]

        let options = candidateCenters.compactMap { center -> (point: NSPoint, score: CGFloat)? in
            let rawOrigin = NSPoint(x: center.x - frame.width / 2, y: center.y - frame.height / 2)
            let origin = clamp(rawOrigin, for: frame.size, in: screen)
            if pointDistance(origin, frame.origin) < wanderArrivalDistance { return nil }
            if !isFrameClear(at: origin, size: frame.size, occupied: occupied) { return nil }
            if firstBlockingWindow(from: frame, to: origin, occupied: occupied) != nil { return nil }
            let optionCenter = NSRect(origin: origin, size: frame.size).center
            if segmentIntersectsRect(optionCenter, finish, expanded) { return nil }
            return (origin, pointDistance(start, optionCenter) + pointDistance(optionCenter, finish))
        }
        return options.min(by: { $0.score < $1.score })?.point
    }

    func isFrameClear(at origin: NSPoint, size: NSSize, occupied: [NSRect]) -> Bool {
        let candidate = NSRect(origin: origin, size: size).insetBy(dx: -8, dy: -8)
        return !occupied.contains(where: { $0.intersects(candidate) })
    }

    func segmentIntersectsRect(_ start: NSPoint, _ end: NSPoint, _ rect: NSRect) -> Bool {
        if rect.contains(start) || rect.contains(end) { return true }
        let bottomLeft = NSPoint(x: rect.minX, y: rect.minY)
        let bottomRight = NSPoint(x: rect.maxX, y: rect.minY)
        let topRight = NSPoint(x: rect.maxX, y: rect.maxY)
        let topLeft = NSPoint(x: rect.minX, y: rect.maxY)
        return segmentsIntersect(start, end, bottomLeft, bottomRight)
            || segmentsIntersect(start, end, bottomRight, topRight)
            || segmentsIntersect(start, end, topRight, topLeft)
            || segmentsIntersect(start, end, topLeft, bottomLeft)
    }

    func segmentsIntersect(_ a: NSPoint, _ b: NSPoint, _ c: NSPoint, _ d: NSPoint) -> Bool {
        let denominator = (b.x - a.x) * (d.y - c.y) - (b.y - a.y) * (d.x - c.x)
        if abs(denominator) < 0.0001 {
            return false
        }
        let numeratorA = (a.y - c.y) * (d.x - c.x) - (a.x - c.x) * (d.y - c.y)
        let numeratorB = (a.y - c.y) * (b.x - a.x) - (a.x - c.x) * (b.y - a.y)
        let uA = numeratorA / denominator
        let uB = numeratorB / denominator
        return uA >= 0 && uA <= 1 && uB >= 0 && uB <= 1
    }

    func pointDistance(_ first: NSPoint, _ second: NSPoint) -> CGFloat {
        return hypot(first.x - second.x, first.y - second.y)
    }

    func openWindowRects(in screen: NSRect) -> [NSRect] {
        guard
            let items = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
                as? [[String: Any]]
        else {
            return []
        }

        let currentPID = ProcessInfo.processInfo.processIdentifier
        return items.compactMap { item in
            if (item[kCGWindowOwnerPID as String] as? pid_t) == currentPID { return nil }
            if (item[kCGWindowLayer as String] as? Int ?? 0) != 0 { return nil }
            if (item[kCGWindowAlpha as String] as? Double ?? 1) <= 0.05 { return nil }
            guard
                let bounds = item[kCGWindowBounds as String] as? [String: Any],
                let x = bounds["X"] as? CGFloat,
                let y = bounds["Y"] as? CGFloat,
                let width = bounds["Width"] as? CGFloat,
                let height = bounds["Height"] as? CGFloat
            else {
                return nil
            }
            if width < 80 || height < 80 { return nil }
            let convertedY = screen.maxY - y - height
            return NSRect(x: x, y: convertedY, width: width, height: height).insetBy(dx: -16, dy: -16)
        }
    }

    func clamp(_ point: NSPoint, for size: NSSize, in screen: NSRect) -> NSPoint {
        return NSPoint(
            x: min(max(point.x, screen.minX + 8), screen.maxX - size.width - 8),
            y: min(max(point.y, screen.minY + 8), screen.maxY - size.height - 8)
        )
    }

    func say(_ text: String) {
        speech.stringValue = text
        speech.isHidden = false
        hideSpeech(after: 3)
    }

    func hideSpeech(after seconds: TimeInterval) {
        hideSpeechWorkItem?.cancel()
        let workItem = DispatchWorkItem { [weak self] in
            self?.speech.isHidden = true
        }
        hideSpeechWorkItem = workItem
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds, execute: workItem)
    }

    func showLureCursorIfNeeded() {
        guard lureWindow == nil else { return }
        let size = NSSize(width: 46, height: 46)
        let lure = NSWindow(
            contentRect: NSRect(origin: NSEvent.mouseLocation, size: size),
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )
        lure.contentView = LureView(frame: NSRect(origin: .zero, size: size))
        lure.isOpaque = false
        lure.backgroundColor = .clear
        lure.level = .floating
        lure.hasShadow = false
        lure.ignoresMouseEvents = true
        lure.orderFront(nil)
        lureWindow = lure
    }

    func updateLureCursor(to mouse: NSPoint) {
        guard let lureWindow else { return }
        lureWindow.setFrameOrigin(NSPoint(x: mouse.x + 8, y: mouse.y - 28))
    }

    func stopLureCursor() {
        lureWindow?.orderOut(nil)
        lureWindow = nil
    }

    @objc func quit() {
        stopLureCursor()
        NSApp.terminate(nil)
    }

    func performPetAction(_ action: String, speech text: String) {
        currentAction = action
        actionTicks = 32
        say(text)
    }

    @objc func petFromMenu() {
        performPetAction("happy", speech: "我收到摸摸了。")
    }

    @objc func playFromMenu() {
        currentAction = "play"
        actionTicks = 0
        wanderTarget = nil
        wanderWaypoint = nil
        wanderPauseTicks = 0
        showLureCursorIfNeeded()
        say("逗猫棒启动，跟着鼠标走。")
    }

    @objc func stopPlayFromMenu() {
        stopLureCursor()
        currentAction = "idle"
        actionTicks = 0
        wanderTarget = nil
        wanderWaypoint = nil
        wanderPauseTicks = 0
        petView.tick(action: currentAction)
        say("陪玩结束，回到待机。")
    }

    @objc func sleepFromMenu() {
        stopLureCursor()
        currentAction = "sleep"
        actionTicks = shortSleepTicks
        wanderTarget = nil
        wanderWaypoint = nil
        wanderPauseTicks = 0
        petView.tick(action: currentAction)
        say("我在桌面边边睡一会儿。")
    }

    func wakeFromSleep(speech text: String) {
        stopLureCursor()
        currentAction = "idle"
        actionTicks = 0
        wanderTarget = nil
        wanderWaypoint = nil
        wanderPauseTicks = 24
        petView.tick(action: currentAction)
        say(text)
    }

    @objc func wakeFromMenu() {
        wakeFromSleep(speech: "醒啦，继续陪你。")
    }

    func promptForText(title: String, message: String, placeholder: String) -> String? {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.addButton(withTitle: "保存")
        alert.addButton(withTitle: "取消")
        let input = NSTextField(frame: NSRect(x: 0, y: 0, width: 260, height: 24))
        input.placeholderString = placeholder
        alert.accessoryView = input
        let response = alert.runModal()
        guard response == .alertFirstButtonReturn else { return nil }
        let value = input.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        return value.isEmpty ? nil : value
    }

    func localISODate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone.current
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ssXXXXX"
        return formatter.string(from: date)
    }

    func splitMinutesAndTitle(_ input: String, defaultMinutes: Int? = nil) -> (minutes: Int, title: String)? {
        let parts = input.split(maxSplits: 1, whereSeparator: { $0 == " " || $0 == "\t" })
        if let first = parts.first, let minutes = Int(first), minutes > 0 {
            let title = parts.count > 1 ? String(parts[1]).trimmingCharacters(in: .whitespacesAndNewlines) : "提醒一下"
            return (minutes, title.isEmpty ? "提醒一下" : title)
        }
        guard let defaultMinutes else { return nil }
        return (defaultMinutes, input)
    }

    func createAssistantItem(
        itemType: String,
        title: String,
        body: String = "",
        dueAt: Date? = nil,
        durationMinutes: Int? = nil,
        successSpeech: String
    ) {
        guard let url = URL(string: "\(apiBaseURL)/assistant/items") else {
            say("小助手地址不对。")
            return
        }
        var payload: [String: Any] = [
            "item_type": itemType,
            "title": title,
            "body": body,
            "source": "desktop",
        ]
        if let petID {
            payload["pet_id"] = petID
        }
        if let ownerID {
            payload["owner_id"] = ownerID
        }
        if let dueAt {
            payload["due_at"] = localISODate(dueAt)
        }
        if let durationMinutes {
            payload["duration_minutes"] = durationMinutes
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        currentAction = "work"
        actionTicks = 32
        petView.tick(action: currentAction)
        say("我来记。")

        URLSession.shared.dataTask(with: request) { [weak self] _, response, error in
            DispatchQueue.main.async {
                if error != nil {
                    self?.say("小助手保存失败，后端好像没接住。")
                    return
                }
                if let http = response as? HTTPURLResponse, http.statusCode >= 400 {
                    self?.say("小助手保存失败，稍后再试。")
                    return
                }
                self?.say(successSpeech)
            }
        }.resume()
    }

    @objc func noteFromMenu() {
        guard let text = promptForText(title: "记事", message: "要让龙虾记下什么？", placeholder: "明天改登录页文案") else { return }
        createAssistantItem(itemType: "note", title: text, successSpeech: "记事本收好啦。")
    }

    @objc func todoFromMenu() {
        guard let text = promptForText(title: "待办", message: "要加什么待办？", placeholder: "写周报") else { return }
        createAssistantItem(itemType: "todo", title: text, successSpeech: "待办加好啦。")
    }

    @objc func alarmFromMenu() {
        guard
            let text = promptForText(title: "提醒", message: "输入“分钟 + 内容”，例如：10 喝水", placeholder: "10 喝水"),
            let parsed = splitMinutesAndTitle(text)
        else {
            say("提醒格式像这样：10 喝水。")
            return
        }
        createAssistantItem(
            itemType: "alarm",
            title: parsed.title,
            dueAt: Date().addingTimeInterval(TimeInterval(parsed.minutes * 60)),
            successSpeech: "提醒设好啦。"
        )
    }

    @objc func focusFromMenu() {
        guard
            let text = promptForText(title: "番茄钟", message: "输入“分钟 + 任务”，例如：25 写 PR 描述", placeholder: "25 写 PR 描述"),
            let parsed = splitMinutesAndTitle(text, defaultMinutes: 25)
        else {
            say("番茄钟格式像这样：25 写 PR 描述。")
            return
        }
        createAssistantItem(
            itemType: "focus",
            title: parsed.title,
            dueAt: Date().addingTimeInterval(TimeInterval(parsed.minutes * 60)),
            durationMinutes: parsed.minutes,
            successSpeech: "番茄钟开始，我陪你。"
        )
    }
}

func argumentValue(_ name: String) -> String? {
    let args = CommandLine.arguments
    guard let index = args.firstIndex(of: name), index + 1 < args.count else {
        return nil
    }
    return args[index + 1]
}

let name = argumentValue("--name") ?? "Desktop Pet"
let imagePath = argumentValue("--image")
let manifestPath = argumentValue("--manifest")
let offsetIndex = Int(argumentValue("--offset-index") ?? "0") ?? 0
let apiBaseURL = argumentValue("--api-base") ?? "http://127.0.0.1:8000"
let petID = Int(argumentValue("--pet-id") ?? "")
let ownerID = Int(argumentValue("--owner-id") ?? "")
let app = NSApplication.shared
let delegate = AppDelegate(
    petName: name,
    imagePath: imagePath,
    manifestPath: manifestPath,
    offsetIndex: offsetIndex,
    apiBaseURL: apiBaseURL,
    petID: petID,
    ownerID: ownerID
)
app.delegate = delegate
app.run()
