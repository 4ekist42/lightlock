#!/usr/bin/env python3
import time, signal, sys, collections, subprocess
from macals import find_sensor

DEBUG = True
HZ = 25.0
MAX_SECONDS = 120.0
JUMP_RATE = 1.0
DERIV_WINDOW = 6
EPS = 1.0
LOCKSCREEN_ON_JUMP = False

def do_lockscreen():
    try:
        subprocess.run(["pmset", "displaysleepnow"], check=False)
    except Exception as e:
        print(f"pmset error: {e}", file=sys.stderr)
    sys.exit(0)

def make_sensor():
    s = find_sensor()
    if s is None:
        print("ALS не найден.", file=sys.stderr)
        sys.exit(1)
    print(f"Датчик: {s.name}", flush=True)
    return s

def run_headless(sensor):
    deriv = collections.deque(maxlen=max(2, DERIV_WINDOW))
    last_t = last_y = None
    period = 1.0 / max(1e-3, HZ)

    def sigint(_, __):
        print("\nCtrl+C", file=sys.stderr)
        sys.exit(0)
    signal.signal(signal.SIGINT, sigint)

    while True:
        y = float(sensor.get_current_lux())
        t = time.monotonic()
        is_jump = False

        if last_t is not None:
            dt = max(1e-6, t - last_t)
            dy = y - last_y
            if abs(dy) >= EPS:
                deriv.append(dy / dt)
                rate = sum(deriv) / len(deriv)
                if abs(rate) >= JUMP_RATE:
                    is_jump = True
                    print(f"[JUMP] t={t:.3f}, lux={y:.2f}, rate={rate:.2f}")

        last_t, last_y = t, y

        if LOCKSCREEN_ON_JUMP and is_jump:
            print("Jump — lock...", file=sys.stderr)
            do_lockscreen()

        time.sleep(period)

def run_with_plot(sensor):
    import matplotlib
    matplotlib.use("MacOSX")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    fig = plt.figure()
    plt.title("Ambient Light")
    plt.xlabel("t, s")
    plt.ylabel("lux")
    (line,) = plt.plot([], [], lw=1.5)
    (jump_pts,) = plt.plot([], [], "o", ms=6)

    t0 = time.monotonic()
    xs, ys = collections.deque(), collections.deque()
    jx, jy = [], []
    deriv = collections.deque(maxlen=max(2, DERIV_WINDOW))
    last_t = last_y = None
    period = 1.0 / max(1e-3, HZ)

    def sigint(_, __):
        print("\nCtrl+C", file=sys.stderr)
        plt.close(fig)
    signal.signal(signal.SIGINT, sigint)

    def update(_):
        nonlocal last_t, last_y
        y = float(sensor.get_current_lux())
        t = time.monotonic() - t0
        is_jump = False

        if last_t is not None:
            dt = max(1e-6, t - last_t)
            dy = y - last_y
            if abs(dy) >= EPS:
                deriv.append(dy / dt)
                rate = sum(deriv) / len(deriv)
                if abs(rate) >= JUMP_RATE:
                    is_jump = True
                    jx.append(t)
                    jy.append(y)

        last_t, last_y = t, y
        xs.append(t)
        ys.append(y)

        while xs and xs[-1] - xs[0] > MAX_SECONDS:
            xs.popleft()
            ys.popleft()

        line.set_data(xs, ys)
        jump_pts.set_data(jx, jy)

        if xs:
            plt.xlim(max(0, xs[-1] - MAX_SECONDS), xs[-1] if xs[-1] > 5 else 5)
            ymin, ymax = min(ys), max(ys)
            if ymin == ymax:
                ymax = ymin + 1
            pad = 0.07 * (ymax - ymin)
            plt.ylim(ymin - pad, ymax + pad)

        if LOCKSCREEN_ON_JUMP and is_jump:
            print("Jump — lock...", file=sys.stderr)
            do_lockscreen()

        time.sleep(period)
        return line, jump_pts

    ani = FuncAnimation(fig, update, interval=1, blit=True, cache_frame_data=False)
    plt.show()

def main():
    s = make_sensor()
    run_with_plot(s) if DEBUG else run_headless(s)

if __name__ == "__main__":
    main()