/*
 * Experimental Vorbis pre-IMDCT spectrum extractor.
 *
 * This translation unit intentionally includes the pinned stb_vorbis source
 * so it can call the decoder's internal packet functions. The
 * STB_VORBIS_SPECTRUM_ONLY build flag stops decoding after inverse channel
 * coupling and floor application, immediately before inverse_mdct().
 */
#define STB_VORBIS_NO_PUSHDATA_API
#define STB_VORBIS_NO_INTEGER_CONVERSION
#define STB_VORBIS_SPECTRUM_ONLY
#include "../third_party/stb/stb_vorbis.c"

#include <errno.h>
#include <stdint.h>

#define FORMAT_VERSION 1u
#define BLOCK_TAG 0x4b434c42u /* "BLCK", little endian */
#define END_TAG 0u

typedef struct SpectrumPacket {
   uint32_t packet_index;
   uint32_t mode_index;
   uint32_t block_size;
   uint32_t previous_block_size;
   uint32_t next_block_size;
   int64_t granule_position;
   float *coefficients;
} SpectrumPacket;

static int write_bytes(FILE *out, const void *data, size_t size)
{
   return fwrite(data, 1, size, out) == size;
}

static int write_u32(FILE *out, uint32_t value)
{
   return write_bytes(out, &value, sizeof(value));
}

static int write_u64(FILE *out, uint64_t value)
{
   return write_bytes(out, &value, sizeof(value));
}

static int write_i64(FILE *out, int64_t value)
{
   return write_bytes(out, &value, sizeof(value));
}

static stb_vorbis *open_spectrum_file(const char *filename, int *error)
{
   FILE *file;
   unsigned int length;
   stb_vorbis *decoder;
   stb_vorbis pending;

#if defined(_WIN32) && defined(__STDC_WANT_SECURE_LIB__)
   if (fopen_s(&file, filename, "rb") != 0)
      file = NULL;
#else
   file = fopen(filename, "rb");
#endif
   if (!file) {
      if (error) *error = VORBIS_file_open_failure;
      return NULL;
   }

   if (fseek(file, 0, SEEK_END) != 0) {
      fclose(file);
      if (error) *error = VORBIS_seek_failed;
      return NULL;
   }
   length = (unsigned int)ftell(file);
   if (fseek(file, 0, SEEK_SET) != 0) {
      fclose(file);
      if (error) *error = VORBIS_seek_failed;
      return NULL;
   }

   vorbis_init(&pending, NULL);
   pending.f = file;
   pending.f_start = 0;
   pending.stream_len = length;
   pending.close_on_free = TRUE;
   if (start_decoder(&pending)) {
      decoder = vorbis_alloc(&pending);
      if (decoder) {
         *decoder = pending;
         return decoder;
      }
   }

   if (error) *error = pending.error;
   vorbis_deinit(&pending);
   return NULL;
}

static int decode_spectrum_packet(
      stb_vorbis *decoder,
      uint32_t packet_index,
      SpectrumPacket *packet)
{
   int left_start, left_end, right_start, right_end, mode;
   int decoded_length;
   int block_size;
   int coefficient_count;
   size_t coefficient_bytes;
   int channel;

   if (!vorbis_decode_initial(
         decoder,
         &left_start,
         &left_end,
         &right_start,
         &right_end,
         &mode))
      return 0;

   block_size = decoder->blocksize[decoder->mode_config[mode].blockflag];
   if (!vorbis_decode_packet_rest(
         decoder,
         &decoded_length,
         decoder->mode_config + mode,
         left_start,
         left_end,
         right_start,
         right_end,
         &left_start))
      return -1;

   coefficient_count = block_size >> 1;
   coefficient_bytes =
      (size_t)decoder->channels * (size_t)coefficient_count * sizeof(float);
   packet->coefficients = (float *)malloc(coefficient_bytes);
   if (!packet->coefficients)
      return -1;

   for (channel = 0; channel < decoder->channels; ++channel) {
      memcpy(
         packet->coefficients + (size_t)channel * (size_t)coefficient_count,
         decoder->channel_buffers[channel],
         (size_t)coefficient_count * sizeof(float));
   }

   packet->packet_index = packet_index;
   packet->mode_index = (uint32_t)mode;
   packet->block_size = (uint32_t)block_size;
   packet->next_block_size = 0;
   packet->granule_position =
      decoder->last_seg_which == decoder->end_seg_with_known_loc
         ? (int64_t)decoder->known_loc_for_packet
         : -1;
   return 1;
}

static int write_packet(FILE *out, const SpectrumPacket *packet, int channels)
{
   uint32_t coefficient_count = packet->block_size >> 1;
   size_t coefficient_bytes =
      (size_t)channels * (size_t)coefficient_count * sizeof(float);
   return
      write_u32(out, BLOCK_TAG) &&
      write_u32(out, packet->packet_index) &&
      write_u32(out, packet->mode_index) &&
      write_u32(out, packet->block_size) &&
      write_u32(out, packet->previous_block_size) &&
      write_u32(out, packet->next_block_size) &&
      write_i64(out, packet->granule_position) &&
      write_bytes(out, packet->coefficients, coefficient_bytes);
}

int main(int argc, char **argv)
{
   const char magic[8] = {'A','D','V','M','D','C','T','1'};
   const char *input_path;
   const char *output_path;
   FILE *out;
   stb_vorbis *decoder;
   stb_vorbis_info info;
   SpectrumPacket previous = {0};
   SpectrumPacket current = {0};
   uint32_t packet_index = 0;
   uint64_t total_samples;
   int decoder_error = VORBIS__no_error;
   int result = 0;
   int ok = 1;

   if (argc != 3) {
      fprintf(stderr, "usage: %s INPUT.ogg OUTPUT.bin\n", argv[0]);
      return 2;
   }
   input_path = argv[1];
   output_path = argv[2];

   decoder = open_spectrum_file(input_path, &decoder_error);
   if (!decoder) {
      fprintf(stderr, "cannot open Vorbis stream (error %d): %s\n",
              decoder_error, input_path);
      return 3;
   }
   info = stb_vorbis_get_info(decoder);
   total_samples = (uint64_t)stb_vorbis_stream_length_in_samples(decoder);

   out = fopen(output_path, "wb");
   if (!out) {
      fprintf(stderr, "cannot create output: %s (%s)\n",
              output_path, strerror(errno));
      stb_vorbis_close(decoder);
      return 4;
   }

   ok =
      write_bytes(out, magic, sizeof(magic)) &&
      write_u32(out, FORMAT_VERSION) &&
      write_u32(out, (uint32_t)info.sample_rate) &&
      write_u32(out, (uint32_t)info.channels) &&
      write_u32(out, (uint32_t)decoder->blocksize_0) &&
      write_u32(out, (uint32_t)decoder->blocksize_1) &&
      write_u64(out, total_samples);

   while (ok && (result = decode_spectrum_packet(
         decoder, packet_index++, &current)) > 0) {
      current.previous_block_size = previous.block_size;
      if (previous.coefficients) {
         previous.next_block_size = current.block_size;
         ok = write_packet(out, &previous, info.channels);
         free(previous.coefficients);
      }
      previous = current;
      memset(&current, 0, sizeof(current));
   }

   if (ok && result < 0) {
      fprintf(stderr, "Vorbis packet decode failed near packet %u\n",
              packet_index);
      ok = 0;
   }
   if (ok && previous.coefficients) {
      ok = write_packet(out, &previous, info.channels);
      free(previous.coefficients);
      previous.coefficients = NULL;
   }
   if (ok)
      ok = write_u32(out, END_TAG);

   if (fclose(out) != 0)
      ok = 0;
   stb_vorbis_close(decoder);

   if (!ok) {
      remove(output_path);
      return 5;
   }
   return 0;
}
