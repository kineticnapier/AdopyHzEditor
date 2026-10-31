using System.IO.Compression;

namespace AdopyHzEditor.AssetExtractor;

internal static class ClassDataCache
{
    private const string ClassDataArtifactUrl =
        "https://nightly.link/AssetRipper/Tpk/workflows/type_tree_tpk/master/lz4_file.zip";

    public static string Resolve()
    {
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string cacheDirectory = Path.Combine(localAppData, "AdopyHzEditor", "AssetExtractor");
        Directory.CreateDirectory(cacheDirectory);

        string targetPath = Path.Combine(cacheDirectory, "classdata.tpk");
        if (IsUsable(targetPath))
            return targetPath;

        string zipPath = Path.Combine(cacheDirectory, $"classdata-{Guid.NewGuid():N}.zip");
        string extractedPath = Path.Combine(cacheDirectory, $"classdata-{Guid.NewGuid():N}.tpk");

        try
        {
            Console.WriteLine("[extract] classdata cache missing; downloading AssetRipper type-tree package...");

            using var client = new HttpClient
            {
                Timeout = TimeSpan.FromMinutes(5)
            };
            client.DefaultRequestHeaders.UserAgent.ParseAdd("AdopyHzEditor.AssetExtractor/1.0");

            using HttpResponseMessage response = client.GetAsync(
                    ClassDataArtifactUrl,
                    HttpCompletionOption.ResponseHeadersRead)
                .GetAwaiter()
                .GetResult();
            response.EnsureSuccessStatusCode();

            using (Stream input = response.Content.ReadAsStream())
            using (FileStream output = File.Create(zipPath))
                input.CopyTo(output);

            using (ZipArchive archive = ZipFile.OpenRead(zipPath))
            {
                ZipArchiveEntry? tpkEntry = archive.Entries.FirstOrDefault(entry =>
                    entry.FullName.EndsWith(".tpk", StringComparison.OrdinalIgnoreCase));
                if (tpkEntry is null)
                    throw new InvalidDataException("Downloaded classdata artifact contains no .tpk file.");

                using Stream input = tpkEntry.Open();
                using FileStream output = File.Create(extractedPath);
                input.CopyTo(output);
            }

            if (!IsUsable(extractedPath))
                throw new InvalidDataException("Extracted classdata.tpk is empty.");

            File.Move(extractedPath, targetPath, true);
            return targetPath;
        }
        finally
        {
            TryDelete(zipPath);
            TryDelete(extractedPath);
        }
    }

    private static bool IsUsable(string path) =>
        File.Exists(path) && new FileInfo(path).Length > 0;

    private static void TryDelete(string path)
    {
        try
        {
            if (File.Exists(path))
                File.Delete(path);
        }
        catch
        {
            // Best-effort cleanup only.
        }
    }
}
