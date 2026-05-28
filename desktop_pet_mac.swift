import AppKit
import CoreGraphics

let transparentColor = NSColor(calibratedRed: 1, green: 0, blue: 1, alpha: 1)
let petSize: CGFloat = 168
let playFollowTicks = 150

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
        menu.addItem(withTitle: "摸摸", action: #selector(AppDelegate.petFromMenu), keyEquivalent: "")
        menu.addItem(withTitle: "陪玩", action: #selector(AppDelegate.playFromMenu), keyEquivalent: "")
        menu.addItem(withTitle: "睡一会儿", action: #selector(AppDelegate.sleepFromMenu), keyEquivalent: "")
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
    var wanderPauseTicks = 0
    var currentAction = "idle"
    var actionTicks = 0
    var hideSpeechWorkItem: DispatchWorkItem?
    var lureWindow: NSWindow?
    let petName: String
    let imagePath: String?
    let manifestPath: String?
    let offsetIndex: Int

    init(petName: String, imagePath: String?, manifestPath: String?, offsetIndex: Int) {
        self.petName = petName
        self.imagePath = imagePath
        self.manifestPath = manifestPath
        self.offsetIndex = offsetIndex
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
        if actionTicks > 0 {
            actionTicks -= 1
            if actionTicks == 0 && currentAction == "play" {
                stopLureCursor()
                currentAction = "idle"
            }
        } else if currentAction != "idle" && currentAction != "sleep" {
            if currentAction == "play" {
                stopLureCursor()
            }
            currentAction = "idle"
        }

        if currentAction == "play" {
            stepPlayFollow(in: screen)
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

        let speed = min(CGFloat(4.2), max(CGFloat(1.2), distance / 40))
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
            currentAction = "relax"
            petView.tick(action: currentAction)
            return
        }

        if shouldChooseNewWanderTarget(from: frame) {
            wanderTarget = chooseWanderTarget(in: screen, currentFrame: frame)
            if Int.random(in: 0..<5) == 0 {
                wanderPauseTicks = Int.random(in: 16...40)
            }
        }

        guard let target = wanderTarget else {
            currentAction = "relax"
            petView.tick(action: currentAction)
            return
        }

        let deltaX = target.x - frame.origin.x
        let deltaY = target.y - frame.origin.y
        if abs(deltaX) < 6 && abs(deltaY) < 6 {
            wanderTarget = nil
            currentAction = "idle"
            wanderPauseTicks = Int.random(in: 12...36)
            petView.tick(action: currentAction)
            return
        }

        let speed: CGFloat = 0.85
        let distance = max(1, hypot(deltaX, deltaY))
        frame.origin.x += deltaX / distance * speed
        frame.origin.y += deltaY / distance * min(speed * 0.35, abs(deltaY))
        frame.origin = clamp(frame.origin, for: frame.size, in: screen)
        dx = deltaX >= 0 ? 1 : -1
        currentAction = deltaX >= 0 ? "walk_right" : "walk_left"
        petView.tick(action: currentAction)
        window.setFrame(frame, display: true)
    }

    func shouldChooseNewWanderTarget(from frame: NSRect) -> Bool {
        guard let target = wanderTarget else { return true }
        if Int.random(in: 0..<460) == 0 { return true }
        return abs(target.x - frame.origin.x) < 6 && abs(target.y - frame.origin.y) < 6
    }

    func chooseWanderTarget(in screen: NSRect, currentFrame: NSRect) -> NSPoint {
        let occupied = openWindowRects(in: screen)
        for _ in 0..<36 {
            let x = CGFloat.random(in: (screen.minX + 20)...max(screen.minX + 20, screen.maxX - currentFrame.width - 20))
            let y = CGFloat.random(in: (screen.minY + 10)...max(screen.minY + 10, screen.maxY - currentFrame.height - 10))
            let candidate = NSRect(origin: NSPoint(x: x, y: y), size: currentFrame.size).insetBy(dx: -24, dy: -16)
            if !occupied.contains(where: { $0.intersects(candidate) }) {
                return NSPoint(x: x, y: y)
            }
        }

        let localX = currentFrame.origin.x + CGFloat.random(in: -46...46)
        let localY = currentFrame.origin.y + CGFloat.random(in: -18...18)
        return clamp(NSPoint(x: localX, y: localY), for: currentFrame.size, in: screen)
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
        actionTicks = playFollowTicks
        wanderTarget = nil
        wanderPauseTicks = 0
        showLureCursorIfNeeded()
        say("逗猫棒启动，跟着鼠标走。")
    }

    @objc func sleepFromMenu() {
        stopLureCursor()
        currentAction = "sleep"
        actionTicks = 0
        say("我在桌面边边睡一会儿。")
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
let app = NSApplication.shared
let delegate = AppDelegate(
    petName: name,
    imagePath: imagePath,
    manifestPath: manifestPath,
    offsetIndex: offsetIndex
)
app.delegate = delegate
app.run()
