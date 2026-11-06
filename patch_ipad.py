"""Apply direct touch input to the pinned experimental runner. AGPL-3.0-or-later."""
from pathlib import Path

p = Path('src/ios/main.c')
s = p.read_text()
def replace(old, new):
    global s
    if s.count(old) != 1:
        raise RuntimeError(f'Expected exactly one patch anchor: {old[:80]}')
    s = s.replace(old, new)

replace('/* TODO: touchscreen mouse support */\nvoid platformGetMousePos(double *xPos, double *yPos) {\n    *xPos = 0.0;\n    *yPos = 0.0;\n}', '''/* Pointer events cross from UIKit to the runner only at frame boundaries.
 * One button transition per frame preserves taps shorter than a game frame. */
typedef struct { double x, y; int edge; } BSPointerEvent;
static BSPointerEvent bsPointerQueue[256];
static unsigned bsPointerHead, bsPointerTail;
static double bsPointerX, bsPointerY;
static UITouch *bsPointerTouch;

static void bsQueuePointer(UITouch *touch, int edge) {
    if (!g_glView) return;
    CGPoint p = [touch locationInView:g_glView];
    CGSize size = g_glView.bounds.size;
    if (size.width <= 0 || size.height <= 0) return;
    BSPointerEvent e = {p.x / size.width, p.y / size.height, edge};
    @synchronized([UIApplication class]) {
        unsigned last = (bsPointerHead + 255) % 256;
        if (edge == 0 && bsPointerHead != bsPointerTail && bsPointerQueue[last].edge == 0) {
            bsPointerQueue[last] = e;
            return;
        }
        unsigned next = (bsPointerHead + 1) % 256;
        if (next == bsPointerTail) {
            /* Recover from overflow with a release; never leave a held button. */
            bsPointerTail = bsPointerHead;
            e.edge = -1;
        }
        bsPointerQueue[bsPointerHead] = e;
        bsPointerHead = next;
    }
}

static void bsDrainPointer(void) {
    if (!g_runner || fbWidth <= 0 || fbHeight <= 0) return;
    @synchronized([UIApplication class]) {
        while (bsPointerTail != bsPointerHead) {
            BSPointerEvent e = bsPointerQueue[bsPointerTail];
            bsPointerTail = (bsPointerTail + 1) % 256;
            bsPointerX = e.x; bsPointerY = e.y;
            Runner_updateMousePosition(g_runner, fbWidth, fbHeight,
                bsPointerX * fbWidth, bsPointerY * fbHeight);
            if (e.edge > 0) RunnerMouse_onButtonDown(g_runner->mouse, GML_MB_LEFT);
            if (e.edge < 0) RunnerMouse_onButtonUp(g_runner->mouse, GML_MB_LEFT);
            if (e.edge != 0) break;
        }
    }
}

void platformGetMousePos(double *xPos, double *yPos) {
    *xPos = bsPointerX * fbWidth;
    *yPos = bsPointerY * fbHeight;
}''')
replace('''    CGRect bounds = [[UIScreen mainScreen] bounds];
    if (bounds.size.width <= 0 || bounds.size.height <= 0) return false;
    *outW = bounds.size.width;
    *outH = bounds.size.height;''', '''    if (fbWidth <= 0 || fbHeight <= 0) return false;
    *outW = fbWidth;
    *outH = fbHeight;''')
replace('    bsDrainKeyEvents();', '    bsDrainKeyEvents();\n    bsDrainPointer();')
replace('    [_dpad drawInContext:ctx];\n    for (int i = 0; i < 3; i++)\n        [_actionButtons[i] drawInContext:ctx];', '    /* Direct pointer controls: do not cover game buttons with a gamepad. */')
replace('''        if ([_dpad handleTouchBegan:touch point:p]) continue;

        for (int i = 0; i < 3; i++) {
            if ([_actionButtons[i] handleTouchBegan:touch point:p]) break;
        }''', '''        CGPoint gamePoint = [touch locationInView:g_glView];
        if (!bsPointerTouch && CGRectContainsPoint(g_glView.bounds, gamePoint)) {
            bsPointerTouch = touch;
            bsQueuePointer(touch, 1);
        }''')
replace('''        CGPoint p = [touch locationInView:self];
        if ([_dpad handleTouchMoved:touch point:p]) {
            [self setNeedsDisplay];
            break;
        }''', '''        if (touch == bsPointerTouch) bsQueuePointer(touch, 0);''')
replace('''- (void)handleTouchEnd:(NSSet *)touches {
    for (UITouch *touch in touches) {''', '''- (void)handleTouchEnd:(NSSet *)touches {
    for (UITouch *touch in touches) {
        if (touch == bsPointerTouch) {
            bsQueuePointer(touch, -1);
            bsPointerTouch = nil;
            continue;
        }''')
replace('''    g_aspectRatio = (reqH > 0) ? ((float)reqW / (float)reqH) : 1.0f;''', '''    @synchronized([UIApplication class]) {
        bsPointerHead = bsPointerTail = 0;
        bsPointerX = bsPointerY = 0;
    }
    g_aspectRatio = (reqH > 0) ? ((float)reqW / (float)reqH) : 1.0f;''')
replace('''static int bsLoadRendererPreference(void) {
    NSInteger v''', '''static int bsLoadRendererPreference(void) {
    if (![[NSUserDefaults standardUserDefaults] objectForKey:BS_RENDERER_DEFAULTS_KEY])
        return BS_RENDERER_MODERN_GL;
    NSInteger v''')
p.write_text(s)
print('Applied direct pointer input and Modern GL default.')

