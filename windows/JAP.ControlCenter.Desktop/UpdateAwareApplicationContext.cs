namespace JAP.ControlCenter.Desktop;

internal sealed class UpdateAwareApplicationContext : ApplicationContext
{
    private readonly MainWindow _window;
    private readonly UpdateCoordinator _updates;

    public UpdateAwareApplicationContext()
    {
        var hostRoot = AppContext.BaseDirectory.TrimEnd(
            Path.DirectorySeparatorChar,
            Path.AltDirectorySeparatorChar);
        var installRoot = Directory.GetParent(hostRoot)?.FullName
            ?? throw new InvalidOperationException(
                "Desktop host installation root could not be resolved for update coordination.");

        _window = new MainWindow();
        _updates = new UpdateCoordinator(_window, installRoot);
        MainForm = _window;
        _window.Shown += OnWindowShown;
        _window.FormClosed += OnWindowClosed;
        _window.Show();
    }

    private void OnWindowShown(object? sender, EventArgs e)
    {
        _updates.StartPolling();
    }

    private void OnWindowClosed(object? sender, FormClosedEventArgs e)
    {
        _updates.Dispose();
        ExitThread();
    }
}
