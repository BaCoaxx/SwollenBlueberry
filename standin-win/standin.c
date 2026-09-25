/* Minimal Win32 window used as a Guild Wars stand-in under Wine.
   Close the window to simulate the client exiting.
   The command line is ignored on purpose: it may contain a game password.
   Build: scripts/build-win-standin.sh
*/
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static const char CLASS_NAME[] = "GWMultiLaunchStandin";

static LRESULT CALLBACK wnd_proc(HWND hwnd, UINT msg, WPARAM wparam, LPARAM lparam) {
    switch (msg) {
    case WM_CLOSE:
        DestroyWindow(hwnd);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hwnd, &ps);
        RECT rect;
        const char *text =
            "GWMultiLaunch stand-in\r\n\r\nClose this window to simulate the client exiting.";
        GetClientRect(hwnd, &rect);
        DrawTextA(hdc, text, -1, &rect, DT_CENTER | DT_VCENTER | DT_WORDBREAK);
        EndPaint(hwnd, &ps);
        return 0;
    }
    default:
        break;
    }
    return DefWindowProcA(hwnd, msg, wparam, lparam);
}

int WINAPI WinMain(HINSTANCE instance, HINSTANCE prev, LPSTR cmdline, int show) {
    WNDCLASSA wc;
    HWND hwnd;
    MSG msg;

    (void)prev;
    (void)cmdline;

    ZeroMemory(&wc, sizeof(wc));
    wc.lpfnWndProc = wnd_proc;
    wc.hInstance = instance;
    wc.lpszClassName = CLASS_NAME;
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    if (!RegisterClassA(&wc)) {
        return 1;
    }

    hwnd = CreateWindowExA(
        0,
        CLASS_NAME,
        "GW stand-in",
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT,
        CW_USEDEFAULT,
        440,
        200,
        NULL,
        NULL,
        instance,
        NULL);
    if (!hwnd) {
        return 1;
    }
    ShowWindow(hwnd, show);
    UpdateWindow(hwnd);

    while (GetMessage(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    return (int)msg.wParam;
}
