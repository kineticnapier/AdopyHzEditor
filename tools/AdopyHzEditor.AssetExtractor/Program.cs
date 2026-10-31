namespace AdopyHzEditor.AssetExtractor;

public static class Program
{
    public static int Main(string[] args)
    {
        try
        {
            Options options = Options.Parse(args);
            if (options.ShowHelp)
            {
                PrintUsage();
                return 0;
            }

            string gameRoot = ValidateGameRoot(options.GameRoot);
            string outputPath = options.OutputPath is not null
                ? Path.GetFullPath(options.OutputPath.Trim('"'))
                : Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "AdopyHzEditor",
                    "AssetCache",
                    "hitsounds",
                    "sndKick.wav");

            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            AdoFaiKickExtractor.Extract(gameRoot, outputPath);
            Console.WriteLine($"[extract] kick={outputPath}");
            return 0;
        }
        catch (ArgumentException ex)
        {
            Console.Error.WriteLine(ex.Message);
            PrintUsage();
            return 2;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"extract fatal: {ex.GetType().Name}: {ex.Message}");
            return 1;
        }
    }

    private static string ValidateGameRoot(string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
            throw new ArgumentException("Missing --adofai <game directory>.");

        string root = Path.GetFullPath(path.Trim('"'));
        string data = Path.Combine(root, "A Dance of Fire and Ice_Data");
        if (!File.Exists(Path.Combine(data, "resources.assets")) ||
            !File.Exists(Path.Combine(data, "resources.assets.resS")))
        {
            throw new DirectoryNotFoundException($"Not an ADOFAI installation directory: {root}");
        }

        return root;
    }

    private static void PrintUsage()
    {
        Console.WriteLine("AdopyHzEditor.AssetExtractor");
        Console.WriteLine();
        Console.WriteLine("Usage:");
        Console.WriteLine("  AdopyHzEditor.AssetExtractor --adofai <game directory> [--output <sndKick.wav>]");
    }

    private sealed record Options(string? GameRoot, string? OutputPath, bool ShowHelp)
    {
        public static Options Parse(string[] args)
        {
            string? gameRoot = null;
            string? outputPath = null;
            bool showHelp = false;

            for (int i = 0; i < args.Length; i++)
            {
                string arg = args[i];
                switch (arg)
                {
                    case "-h":
                    case "--help":
                        showHelp = true;
                        break;
                    case "--adofai":
                        gameRoot = RequireValue(args, ref i, arg);
                        break;
                    case "--output":
                        outputPath = RequireValue(args, ref i, arg);
                        break;
                    default:
                        throw new ArgumentException($"Unknown option: {arg}");
                }
            }

            return new Options(gameRoot, outputPath, showHelp);
        }

        private static string RequireValue(string[] args, ref int index, string option)
        {
            if (index + 1 >= args.Length)
                throw new ArgumentException($"Missing value for {option}");
            return args[++index];
        }
    }
}
