using System.Text;
using AssetsTools.NET;
using AssetsTools.NET.Extra;
using Fmod5Sharp;
using NVorbis;

namespace AdopyHzEditor.AssetExtractor;

internal static class AdoFaiKickExtractor
{
    public static void Extract(string gameRoot, string outputPath)
    {
        string root = Path.GetFullPath(gameRoot.Trim('"'));
        string dataDirectory = Path.Combine(root, "A Dance of Fire and Ice_Data");
        string resourcesPath = Path.Combine(dataDirectory, "resources.assets");
        if (!File.Exists(resourcesPath))
            throw new FileNotFoundException("ADOFAI resources.assets was not found.", resourcesPath);

        string classDataPath = ClassDataCache.Resolve();
        var manager = new AssetsManager();
        try
        {
            manager.LoadClassPackage(classDataPath);
            AssetsFileInstance instance = manager.LoadAssetsFile(resourcesPath, false);
            manager.LoadClassDatabaseFromPackage(instance.file.Metadata.UnityVersion);

            AssetFileInfo? kickInfo = null;
            foreach (AssetFileInfo info in instance.file.GetAssetsOfType(AssetClassID.AudioClip))
            {
                AssetTypeValueField rootField = manager.GetBaseField(instance, info);
                AssetTypeValueField nameField = rootField["m_Name"];
                if (!nameField.IsDummy &&
                    string.Equals(nameField.AsString, "sndKick", StringComparison.OrdinalIgnoreCase))
                {
                    kickInfo = info;
                    break;
                }
            }

            if (kickInfo is null)
                throw new InvalidDataException("ADOFAI AudioClip 'sndKick' was not found.");

            ExtractClip(manager, instance, kickInfo, dataDirectory, outputPath);
        }
        finally
        {
            manager.UnloadAll(true);
        }
    }

    private static void ExtractClip(
        AssetsManager manager,
        AssetsFileInstance instance,
        AssetFileInfo clipInfo,
        string dataDirectory,
        string outputPath)
    {
        AssetTypeValueField clip = manager.GetBaseField(instance, clipInfo);
        AssetTypeValueField resource = clip["m_Resource"];
        if (resource.IsDummy)
            throw new InvalidDataException("sndKick m_Resource could not be decoded.");

        string source = resource["m_Source"].AsString;
        ulong offset = ReadUnsigned(resource["m_Offset"], "m_Offset");
        ulong size = ReadUnsigned(resource["m_Size"], "m_Size");
        if (size == 0 || size > int.MaxValue)
            throw new InvalidDataException($"sndKick resource size is invalid: {size} bytes.");

        string resourcePath = ResolveResourcePath(dataDirectory, source);
        byte[] fsb = ReadResourceRange(resourcePath, offset, checked((int)size));
        if (fsb.Length < 4 ||
            fsb[0] != (byte)'F' ||
            fsb[1] != (byte)'S' ||
            fsb[2] != (byte)'B' ||
            fsb[3] != (byte)'5')
        {
            throw new InvalidDataException(
                $"sndKick resource payload is not FSB5: {Path.GetFileName(resourcePath)} offset={offset} size={size}.");
        }

        var bank = FsbLoader.LoadFsbFromByteArray(fsb);
        if (bank.Samples.Count == 0)
            throw new InvalidDataException("sndKick FSB5 contains no samples.");

        var sample = bank.Samples[0];
        if (!sample.RebuildAsStandardFileFormat(out byte[]? rebuilt, out string? extension) ||
            rebuilt is null ||
            rebuilt.Length == 0 ||
            string.IsNullOrWhiteSpace(extension))
        {
            throw new NotSupportedException(
                $"sndKick FSB5 codec {bank.Header.AudioType} could not be rebuilt.");
        }

        string tempPath = outputPath + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            if (string.Equals(extension, "wav", StringComparison.OrdinalIgnoreCase))
            {
                File.WriteAllBytes(tempPath, rebuilt);
            }
            else if (string.Equals(extension, "ogg", StringComparison.OrdinalIgnoreCase))
            {
                ConvertVorbisToPcm16Wave(rebuilt, tempPath);
            }
            else
            {
                throw new NotSupportedException(
                    $"sndKick FSB5 codec {bank.Header.AudioType} rebuilt as unsupported format '{extension}'.");
            }

            File.Move(tempPath, outputPath, true);
        }
        finally
        {
            try
            {
                if (File.Exists(tempPath))
                    File.Delete(tempPath);
            }
            catch
            {
                // Best-effort cleanup only.
            }
        }
    }

    private static string ResolveResourcePath(string dataDirectory, string source)
    {
        if (string.IsNullOrWhiteSpace(source))
            throw new InvalidDataException("sndKick m_Resource.m_Source is empty.");

        string normalized = source.Replace('/', Path.DirectorySeparatorChar);
        string candidate = Path.IsPathRooted(normalized)
            ? Path.GetFullPath(normalized)
            : Path.GetFullPath(Path.Combine(dataDirectory, normalized));
        if (File.Exists(candidate))
            return candidate;

        string fileNameCandidate = Path.Combine(dataDirectory, Path.GetFileName(normalized));
        if (File.Exists(fileNameCandidate))
            return fileNameCandidate;

        throw new FileNotFoundException("sndKick resource file was not found.", candidate);
    }

    private static byte[] ReadResourceRange(string path, ulong offset, int size)
    {
        using FileStream stream = File.OpenRead(path);
        if (offset > (ulong)stream.Length || offset + (ulong)size > (ulong)stream.Length)
        {
            throw new InvalidDataException(
                $"sndKick resource range is outside {Path.GetFileName(path)}: offset={offset} size={size} length={stream.Length}.");
        }

        stream.Position = checked((long)offset);
        byte[] data = new byte[size];
        stream.ReadExactly(data);
        return data;
    }

    private static ulong ReadUnsigned(AssetTypeValueField field, string fieldName)
    {
        if (field.IsDummy)
            throw new InvalidDataException($"sndKick {fieldName} could not be decoded.");

        return field.TemplateField.ValueType switch
        {
            AssetValueType.UInt64 => field.AsULong,
            AssetValueType.Int64 => checked((ulong)field.AsLong),
            AssetValueType.UInt32 => field.AsUInt,
            AssetValueType.Int32 => checked((ulong)field.AsInt),
            _ => throw new InvalidDataException(
                $"sndKick {fieldName} has unsupported serialized type {field.TemplateField.ValueType}.")
        };
    }

    private static void ConvertVorbisToPcm16Wave(byte[] ogg, string destination)
    {
        using var source = new MemoryStream(ogg, writable: false);
        using var reader = new VorbisReader(source, closeOnDispose: false);
        int channels = reader.Channels;
        int sampleRate = reader.SampleRate;
        if (channels <= 0 || sampleRate <= 0)
            throw new InvalidDataException(
                $"Decoded Vorbis metadata is invalid: channels={channels}, sampleRate={sampleRate}.");

        using var pcm = new MemoryStream();
        using (var writer = new BinaryWriter(pcm, Encoding.ASCII, leaveOpen: true))
        {
            float[] samples = new float[Math.Max(4096, channels * 4096)];
            while (true)
            {
                int read = reader.ReadSamples(samples, 0, samples.Length);
                if (read <= 0)
                    break;

                for (int i = 0; i < read; i++)
                {
                    float value = Math.Clamp(samples[i], -1f, 1f);
                    short pcm16 = value <= -1f
                        ? short.MinValue
                        : value >= 1f
                            ? short.MaxValue
                            : (short)MathF.Round(value * short.MaxValue);
                    writer.Write(pcm16);
                }
            }
            writer.Flush();
        }

        WritePcm16Wave(destination, channels, sampleRate, pcm.ToArray());
    }

    private static void WritePcm16Wave(string path, int channels, int sampleRate, byte[] pcm)
    {
        const short bitsPerSample = 16;
        short blockAlign = checked((short)(channels * (bitsPerSample / 8)));
        int byteRate = checked(sampleRate * blockAlign);
        int riffSize = checked(36 + pcm.Length);

        using FileStream output = File.Create(path);
        using var writer = new BinaryWriter(output, Encoding.ASCII, leaveOpen: false);
        writer.Write(Encoding.ASCII.GetBytes("RIFF"));
        writer.Write(riffSize);
        writer.Write(Encoding.ASCII.GetBytes("WAVE"));
        writer.Write(Encoding.ASCII.GetBytes("fmt "));
        writer.Write(16);
        writer.Write((short)1);
        writer.Write(checked((short)channels));
        writer.Write(sampleRate);
        writer.Write(byteRate);
        writer.Write(blockAlign);
        writer.Write(bitsPerSample);
        writer.Write(Encoding.ASCII.GetBytes("data"));
        writer.Write(pcm.Length);
        writer.Write(pcm);
    }
}
