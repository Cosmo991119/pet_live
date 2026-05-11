import AppKit

let transparentColor = NSColor(calibratedRed: 1, green: 0, blue: 1, alpha: 1)
let petSize: CGFloat = 168

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

        drawShadow()
        if !imageView.isHidden { return }

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
        } else if action == "pet" {
            animationName = "pet"
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
    var currentAction = "idle"
    var actionTicks = 0
    let petName: String
    let imagePath: String?
    let manifestPath: String?

    init(petName: String, imagePath: String?, manifestPath: String?) {
        self.petName = petName
        self.imagePath = imagePath
        self.manifestPath = manifestPath
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
            self?.performPetAction("pet", speech: "摸摸收到。")
        }
        content.addSubview(petView)

        let screenFrame = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1200, height: 800)
        let origin = NSPoint(x: screenFrame.maxX - 300, y: screenFrame.minY + 80)
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

        timer = Timer.scheduledTimer(withTimeInterval: 0.12, repeats: true) { [weak self] _ in
            self?.step()
        }
    }

    func step() {
        guard let screen = NSScreen.main?.visibleFrame else { return }
        petView.tick(action: currentAction)
        if actionTicks > 0 {
            actionTicks -= 1
        } else if currentAction != "idle" && currentAction != "sleep" {
            currentAction = "idle"
        }
        var frame = window.frame
        let speed: CGFloat = currentAction == "play" ? 2.4 : currentAction == "sleep" ? 0 : 0.9
        if frame.minX <= screen.minX + 10 || frame.maxX >= screen.maxX - 10 {
            dx *= -1
        }
        if Int.random(in: 0..<120) == 0 {
            dx *= -1
        }
        frame.origin.x += dx * speed
        window.setFrame(frame, display: true)
    }

    func say(_ text: String) {
        speech.stringValue = text
        speech.isHidden = false
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) { [weak self] in
            self?.speech.isHidden = true
        }
    }

    @objc func quit() {
        NSApp.terminate(nil)
    }

    func performPetAction(_ action: String, speech text: String) {
        currentAction = action
        actionTicks = 32
        say(text)
    }

    @objc func petFromMenu() {
        performPetAction("pet", speech: "我收到摸摸了。")
    }

    @objc func playFromMenu() {
        performPetAction("play", speech: "陪玩模式启动。")
    }

    @objc func sleepFromMenu() {
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
let app = NSApplication.shared
let delegate = AppDelegate(petName: name, imagePath: imagePath, manifestPath: manifestPath)
app.delegate = delegate
app.run()
