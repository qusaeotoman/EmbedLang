#ifndef EMBED_CLAB_INIT_DETAIL_H
#define EMBED_CLAB_INIT_DETAIL_H
#include "stm32f4xx_hal.h"
HAL_StatusTypeDef embed_init_hal(const char *file, uint32_t line);
HAL_StatusTypeDef embed_init_osc(RCC_OscInitTypeDef *config, const char *file, uint32_t line);
HAL_StatusTypeDef embed_init_clock(RCC_ClkInitTypeDef *config, uint32_t latency,
                                   const char *file, uint32_t line);
HAL_StatusTypeDef embed_init_iwdg(IWDG_HandleTypeDef *handle, const char *file, uint32_t line);
void embed_init_note_return(const char *function, const char *file, uint32_t line,
                            HAL_StatusTypeDef status);
void embed_init_note_handler(void);
void embed_init_report(void);
#ifdef EMBED_PLL_RECOVERY
uint32_t embed_init_application_allowed(void);
uint32_t embed_init_pll_recovered(void);
#endif
#endif
