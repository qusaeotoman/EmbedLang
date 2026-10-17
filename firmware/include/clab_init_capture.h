/* Force-included ONLY for board_main.c and the original Core/Src/iwdg.c in
 * --diagnostic init. Never include this in HAL driver definitions. */
#ifndef EMBED_CLAB_INIT_CAPTURE_H
#define EMBED_CLAB_INIT_CAPTURE_H
#include "clab_init_detail.h"
#define HAL_Init() embed_init_hal(__FILE__, __LINE__)
#define HAL_RCC_OscConfig(config) embed_init_osc((config), __FILE__, __LINE__)
#define HAL_RCC_ClockConfig(config, latency) embed_init_clock((config), (latency), __FILE__, __LINE__)
#define HAL_IWDG_Init(handle) embed_init_iwdg((handle), __FILE__, __LINE__)
#endif
