#ifndef EMBED_CLAB_DIAGNOSTICS_H
#define EMBED_CLAB_DIAGNOSTICS_H
#include <stdint.h>
void embed_diagnostic_init_error(void);
void embed_diagnostic_run(void);
#ifdef EMBED_DIAGNOSTIC_INIT
void embed_diagnostic_init_text(const char *text);
void embed_diagnostic_init_value(const char *format, uint32_t value);
#endif
#endif
