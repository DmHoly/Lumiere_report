from __future__ import annotations
from pathlib import Path

def _load_js_asset(cdn_url: str, local_candidates: list) -> str:
    """
    Charge un asset JS : d'abord depuis un fichier local (embarqué inline),
    sinon retourne une balise <script src=CDN>.
    Compatible file:// (pas de CORS).
    """
    from pathlib import Path
    for candidate in local_candidates:
        p = Path(candidate)
        if not p.is_absolute():
            p = Path(__file__).parent / candidate
        if p.exists():
            src = p.read_text(encoding='utf-8')
            return f'<script>/* {p.name} */\n{src}\n</script>'
    return f'<script src="{cdn_url}"></script>'


_PLOTLY_JS = _load_js_asset(
    cdn_url='https://cdn.plot.ly/plotly-2.35.2.min.js',
    local_candidates=[
        'plotly-2.35.2.min.js',
        'assets/plotly-2.35.2.min.js',
        'js/plotly-2.35.2.min.js',
        '../plotly-2.35.2.min.js',
    ]
)

_MARKED_JS = _load_js_asset(
    cdn_url='https://cdn.jsdelivr.net/npm/marked/marked.min.js',
    local_candidates=[
        'marked.min.js',
        'assets/marked.min.js',
    ]
)

# ── Logo Aledia vectoriel inline ─────────────────────────────────────────────
# Logo officiel Aledia : UN seul path avec fill-rule="evenodd".
# Les sous-chemins intérieurs créent les contre-formes de la signature
# via la règle pair-impair — NE PAS découper en paths séparés.
# viewBox="0 0 807 332" (source officielle).
# L'easter egg anime style.color du SVG (currentColor) au clic,
# pas le fill des paths individuels.

AL_D = """M 520 63 L 518 61 L 518 60 L 512 54 L 511 54 L 507 51 L 505 51 L 502 49 L 498 49 L 497 48 L 484 48 L 483 49 L 477 49 L 476 50 L 474 50 L 473 51 L 469 51 L 468 52 L 466 52 L 465 53 L 463 53 L 462 54 L 457 55 L 454 57 L 452 57 L 447 60 L 445 60 L 443 62 L 436 65 L 434 67 L 431 68 L 429 70 L 428 70 L 426 72 L 425 72 L 422 75 L 421 75 L 418 78 L 417 78 L 412 83 L 411 83 L 393 101 L 393 102 L 387 108 L 387 109 L 383 113 L 383 114 L 377 121 L 377 122 L 375 124 L 375 125 L 373 127 L 373 128 L 367 136 L 366 139 L 364 141 L 364 142 L 362 144 L 360 149 L 358 151 L 355 158 L 353 160 L 353 162 L 351 164 L 351 165 L 348 170 L 348 172 L 346 174 L 345 179 L 343 181 L 342 186 L 340 189 L 340 191 L 338 194 L 337 199 L 335 202 L 335 205 L 334 206 L 334 209 L 331 212 L 329 212 L 328 213 L 324 213 L 321 215 L 316 215 L 315 216 L 311 216 L 310 217 L 307 217 L 306 218 L 300 218 L 299 219 L 297 219 L 296 220 L 289 220 L 288 221 L 287 220 L 287 219 L 289 216 L 289 213 L 290 212 L 290 209 L 292 206 L 292 203 L 293 202 L 293 200 L 294 199 L 295 194 L 297 191 L 297 188 L 299 185 L 300 180 L 303 175 L 303 173 L 305 170 L 305 168 L 308 163 L 308 161 L 311 156 L 311 154 L 312 153 L 312 152 L 313 151 L 313 150 L 314 149 L 314 148 L 315 147 L 315 146 L 316 145 L 316 144 L 317 143 L 317 142 L 318 141 L 318 140 L 319 139 L 319 138 L 320 137 L 320 136 L 321 135 L 321 134 L 322 133 L 322 132 L 323 131 L 323 130 L 324 129 L 324 128 L 325 127 L 325 126 L 326 125 L 326 124 L 327 123 L 327 122 L 328 121 L 331 114 L 333 112 L 333 110 L 334 109 L 334 108 L 336 106 L 339 99 L 341 97 L 341 96 L 342 95 L 342 94 L 343 93 L 343 92 L 344 91 L 347 84 L 349 82 L 349 81 L 351 78 L 351 76 L 353 74 L 353 72 L 354 71 L 354 70 L 356 68 L 356 66 L 357 65 L 357 64 L 359 61 L 359 59 L 361 56 L 361 54 L 362 53 L 362 49 L 363 48 L 363 46 L 364 45 L 364 44 L 363 43 L 363 39 L 362 38 L 362 34 L 359 30 L 359 29 L 355 25 L 354 25 L 349 22 L 347 22 L 346 21 L 338 21 L 337 22 L 333 22 L 330 24 L 327 24 L 325 26 L 323 26 L 322 27 L 321 27 L 320 28 L 319 28 L 318 29 L 311 32 L 309 34 L 306 35 L 304 37 L 301 38 L 295 43 L 294 43 L 288 48 L 287 48 L 281 53 L 280 53 L 270 62 L 269 62 L 265 66 L 264 66 L 259 71 L 258 71 L 253 76 L 252 76 L 244 84 L 243 84 L 237 90 L 236 90 L 220 106 L 219 106 L 182 143 L 182 144 L 171 155 L 171 156 L 157 171 L 157 172 L 153 176 L 153 177 L 149 181 L 149 182 L 140 192 L 140 193 L 137 196 L 137 197 L 134 200 L 134 201 L 130 205 L 130 206 L 127 209 L 127 210 L 124 213 L 124 214 L 118 221 L 118 222 L 113 228 L 113 229 L 111 231 L 111 232 L 109 234 L 109 235 L 107 237 L 107 238 L 104 241 L 103 244 L 101 246 L 101 247 L 99 249 L 99 250 L 97 252 L 97 253 L 91 261 L 90 264 L 86 269 L 85 272 L 81 277 L 81 278 L 78 282 L 76 287 L 74 289 L 73 292 L 71 294 L 71 295 L 70 296 L 67 303 L 65 305 L 65 306 L 64 307 L 64 308 L 63 309 L 63 310 L 62 311 L 59 318 L 57 320 L 57 321 L 56 322 L 56 323 L 55 324 L 55 325 L 54 326 L 54 327 L 53 328 L 53 329 L 52 330 L 52 331 L 51 332 L 51 333 L 50 334 L 50 335 L 49 336 L 49 337 L 48 338 L 48 339 L 47 340 L 47 341 L 46 342 L 46 343 L 40 354 L 40 356 L 37 361 L 37 363 L 36 364 L 36 365 L 35 366 L 35 368 L 34 369 L 35 374 L 39 378 L 40 378 L 41 379 L 45 379 L 46 378 L 48 378 L 51 375 L 51 373 L 53 371 L 53 369 L 54 368 L 54 367 L 56 364 L 56 362 L 57 361 L 57 360 L 58 359 L 58 358 L 64 347 L 64 345 L 66 343 L 66 342 L 67 341 L 67 339 L 69 337 L 69 336 L 70 335 L 73 328 L 75 326 L 75 325 L 76 324 L 76 323 L 77 322 L 77 321 L 78 320 L 81 313 L 83 311 L 85 306 L 87 304 L 89 299 L 91 297 L 93 292 L 95 290 L 96 287 L 98 285 L 98 284 L 101 280 L 102 277 L 104 275 L 104 274 L 106 272 L 106 271 L 108 269 L 108 268 L 111 265 L 113 265 L 114 264 L 118 264 L 119 263 L 123 263 L 124 262 L 126 262 L 127 261 L 132 261 L 133 260 L 137 260 L 138 259 L 141 259 L 142 258 L 149 258 L 152 256 L 159 256 L 160 255 L 167 255 L 168 254 L 170 254 L 171 253 L 178 253 L 179 252 L 186 252 L 187 251 L 191 251 L 192 250 L 200 250 L 201 249 L 207 249 L 208 248 L 214 248 L 215 247 L 224 247 L 225 246 L 229 246 L 230 245 L 239 245 L 240 244 L 250 244 L 251 243 L 256 243 L 257 242 L 262 242 L 263 243 L 263 245 L 262 246 L 262 252 L 261 253 L 261 255 L 260 256 L 260 263 L 259 264 L 259 272 L 258 273 L 258 277 L 257 278 L 257 323 L 258 324 L 258 327 L 259 328 L 259 334 L 260 335 L 260 340 L 262 343 L 262 346 L 263 347 L 263 350 L 265 353 L 266 358 L 267 359 L 267 360 L 268 361 L 268 362 L 269 363 L 272 370 L 274 372 L 275 375 L 277 377 L 277 378 L 279 380 L 279 381 L 285 388 L 285 389 L 298 402 L 299 402 L 306 408 L 307 408 L 309 410 L 312 411 L 314 413 L 315 413 L 320 416 L 322 416 L 324 418 L 326 418 L 327 419 L 329 419 L 332 421 L 335 421 L 336 422 L 338 422 L 339 423 L 342 423 L 343 424 L 351 424 L 352 425 L 355 425 L 356 426 L 364 426 L 365 425 L 367 425 L 368 424 L 369 424 L 372 421 L 372 419 L 373 418 L 373 415 L 372 414 L 372 412 L 369 409 L 368 409 L 365 407 L 350 407 L 349 406 L 345 406 L 344 405 L 342 405 L 341 404 L 338 404 L 335 402 L 330 401 L 329 400 L 322 397 L 320 395 L 317 394 L 309 387 L 308 387 L 296 374 L 296 373 L 291 367 L 289 362 L 287 360 L 287 359 L 284 354 L 284 352 L 281 347 L 281 344 L 279 341 L 279 338 L 278 337 L 278 333 L 277 332 L 277 329 L 276 328 L 276 320 L 275 319 L 275 305 L 274 304 L 274 297 L 275 296 L 275 282 L 276 281 L 276 270 L 277 269 L 277 266 L 278 265 L 278 259 L 279 258 L 279 252 L 280 251 L 280 249 L 281 248 L 281 243 L 284 239 L 290 239 L 291 238 L 295 238 L 296 237 L 302 237 L 303 236 L 305 236 L 306 235 L 312 235 L 313 234 L 317 234 L 318 233 L 321 233 L 322 232 L 325 232 L 326 231 L 327 232 L 327 235 L 326 236 L 326 243 L 325 244 L 325 247 L 324 248 L 324 278 L 325 279 L 325 282 L 326 283 L 326 287 L 327 288 L 327 291 L 329 293 L 329 296 L 331 298 L 331 300 L 334 303 L 335 306 L 344 315 L 345 315 L 347 317 L 348 317 L 349 318 L 350 318 L 361 324 L 364 324 L 365 325 L 368 325 L 371 327 L 377 327 L 378 328 L 405 328 L 406 327 L 414 327 L 415 326 L 417 326 L 418 325 L 423 325 L 424 324 L 428 324 L 431 322 L 434 322 L 435 321 L 437 321 L 438 320 L 440 320 L 441 319 L 443 319 L 444 318 L 446 318 L 447 317 L 448 317 L 448 315 L 447 314 L 446 314 L 440 308 L 439 308 L 436 304 L 435 304 L 434 303 L 432 303 L 431 304 L 429 304 L 428 305 L 426 305 L 425 306 L 421 306 L 418 308 L 413 308 L 412 309 L 404 309 L 403 310 L 398 310 L 397 311 L 388 311 L 387 310 L 382 310 L 381 309 L 374 309 L 373 308 L 370 308 L 367 306 L 362 305 L 360 303 L 358 303 L 355 300 L 354 300 L 349 295 L 349 294 L 347 292 L 347 291 L 346 290 L 346 288 L 344 285 L 344 282 L 343 281 L 343 276 L 342 275 L 342 268 L 341 267 L 341 261 L 342 260 L 342 252 L 343 251 L 343 243 L 344 242 L 344 237 L 345 236 L 345 233 L 346 232 L 346 228 L 349 225 L 352 225 L 353 224 L 356 224 L 359 222 L 362 222 L 363 221 L 365 221 L 368 219 L 371 219 L 374 217 L 376 217 L 377 216 L 380 216 L 382 214 L 384 214 L 385 213 L 387 213 L 390 211 L 392 211 L 397 208 L 399 208 L 400 207 L 401 207 L 402 206 L 403 206 L 404 205 L 405 205 L 406 204 L 407 204 L 408 203 L 409 203 L 410 202 L 411 202 L 412 201 L 413 201 L 414 200 L 415 200 L 416 199 L 417 199 L 418 198 L 425 195 L 427 193 L 428 193 L 432 190 L 435 189 L 437 187 L 438 187 L 440 185 L 441 185 L 443 183 L 444 183 L 446 181 L 447 181 L 449 179 L 450 179 L 452 177 L 453 177 L 455 175 L 456 175 L 459 172 L 460 172 L 463 169 L 464 169 L 467 166 L 468 166 L 472 162 L 473 162 L 487 149 L 488 149 L 488 148 L 489 147 L 490 147 L 497 140 L 497 139 L 506 129 L 507 126 L 510 123 L 512 118 L 514 116 L 514 115 L 517 110 L 517 108 L 519 105 L 519 103 L 520 102 L 520 100 L 521 99 L 521 97 L 522 96 L 522 92 L 523 91 L 523 88 L 524 87 L 524 75 L 523 74 L 523 71 L 522 70 L 522 67 L 521 66 Z
      M 345 40 L 345 48 L 343 50 L 343 52 L 342 53 L 342 55 L 340 58 L 340 60 L 337 64 L 337 66 L 336 67 L 334 72 L 332 74 L 332 76 L 331 77 L 331 78 L 329 80 L 326 87 L 324 89 L 324 91 L 322 93 L 322 94 L 321 95 L 321 96 L 320 97 L 320 98 L 319 99 L 316 106 L 314 108 L 314 109 L 313 110 L 313 111 L 312 112 L 312 113 L 311 114 L 311 115 L 310 116 L 310 117 L 309 118 L 306 125 L 304 127 L 304 129 L 301 133 L 301 135 L 300 136 L 300 137 L 298 139 L 298 141 L 294 148 L 294 150 L 293 151 L 293 152 L 290 157 L 290 159 L 287 164 L 287 166 L 286 167 L 286 168 L 285 169 L 285 171 L 283 174 L 282 179 L 280 182 L 280 184 L 279 185 L 279 187 L 278 188 L 278 190 L 277 191 L 277 193 L 276 194 L 276 196 L 275 197 L 275 199 L 274 200 L 274 202 L 273 203 L 273 206 L 272 207 L 272 209 L 271 210 L 271 213 L 270 214 L 270 216 L 269 217 L 269 219 L 268 220 L 268 222 L 267 223 L 265 223 L 264 224 L 261 224 L 260 225 L 249 225 L 248 226 L 237 226 L 236 227 L 233 227 L 232 228 L 222 228 L 221 229 L 212 229 L 211 230 L 208 230 L 207 231 L 198 231 L 197 232 L 191 232 L 190 233 L 185 233 L 184 234 L 176 234 L 175 235 L 173 235 L 172 236 L 165 236 L 164 237 L 157 237 L 156 238 L 154 238 L 153 239 L 146 239 L 145 240 L 141 240 L 140 241 L 137 241 L 136 242 L 130 242 L 129 243 L 127 243 L 126 244 L 125 243 L 125 242 L 128 239 L 128 238 L 130 236 L 130 235 L 133 232 L 134 229 L 137 226 L 137 225 L 140 222 L 140 221 L 143 218 L 143 217 L 147 213 L 147 212 L 154 204 L 154 203 L 159 198 L 159 197 L 162 194 L 162 193 L 172 182 L 172 181 L 179 174 L 179 173 L 187 165 L 187 164 L 199 152 L 199 151 L 229 121 L 230 121 L 245 106 L 246 106 L 254 98 L 255 98 L 261 92 L 262 92 L 268 86 L 269 86 L 274 81 L 275 81 L 281 75 L 282 75 L 285 72 L 286 72 L 291 67 L 292 67 L 295 64 L 296 64 L 298 62 L 299 62 L 302 59 L 303 59 L 305 57 L 306 57 L 314 51 L 317 50 L 319 48 L 320 48 L 321 47 L 322 47 L 333 41 L 335 41 L 336 40 L 339 40 L 340 39 L 344 39 Z
      M 504 71 L 504 72 L 505 73 L 505 76 L 506 77 L 506 84 L 505 85 L 505 90 L 504 91 L 504 93 L 503 94 L 502 99 L 499 104 L 499 106 L 497 108 L 495 113 L 493 115 L 493 116 L 491 118 L 491 119 L 488 122 L 488 123 L 482 129 L 482 130 L 479 133 L 478 133 L 470 141 L 469 141 L 463 147 L 462 147 L 458 151 L 457 151 L 453 155 L 452 155 L 449 158 L 448 158 L 446 160 L 445 160 L 442 163 L 441 163 L 433 169 L 430 170 L 427 173 L 426 173 L 422 176 L 417 178 L 415 180 L 414 180 L 413 181 L 406 184 L 404 186 L 402 186 L 395 190 L 393 190 L 391 192 L 389 192 L 384 195 L 382 195 L 379 197 L 374 198 L 371 200 L 369 200 L 368 201 L 366 201 L 365 202 L 363 202 L 362 203 L 360 203 L 359 204 L 357 204 L 356 205 L 355 205 L 354 204 L 354 202 L 356 199 L 356 197 L 359 192 L 359 189 L 361 187 L 362 182 L 364 180 L 364 179 L 365 178 L 365 176 L 367 174 L 367 172 L 370 168 L 370 166 L 372 164 L 375 157 L 377 155 L 377 154 L 380 150 L 381 147 L 383 145 L 383 144 L 385 142 L 385 141 L 388 138 L 389 135 L 392 132 L 392 131 L 398 124 L 398 123 L 403 118 L 403 117 L 407 113 L 407 112 L 420 99 L 421 99 L 427 93 L 428 93 L 432 89 L 433 89 L 435 87 L 436 87 L 444 81 L 445 81 L 456 75 L 458 75 L 463 72 L 466 72 L 467 71 L 468 71 L 469 70 L 471 70 L 472 69 L 476 69 L 479 67 L 486 67 L 487 66 L 493 66 L 494 67 L 499 67 L 500 68 L 501 68 Z"""

ED_D = """M 308 10 L 306 11 L 303 14 L 302 17 L 301 23 L 300 33 L 298 38 L 298 43 L 297 48 L 295 53 L 294 63 L 292 67 L 289 84 L 283 106 L 278 122 L 275 130 L 273 135 L 271 137 L 269 136 L 265 133 L 261 131 L 258 130 L 253 129 L 248 128 L 235 128 L 229 129 L 222 130 L 218 131 L 211 133 L 203 136 L 189 143 L 180 149 L 176 152 L 165 163 L 162 167 L 160 170 L 158 173 L 155 179 L 153 184 L 152 189 L 152 203 L 153 207 L 154 210 L 155 212 L 156 214 L 158 217 L 164 223 L 154 225 L 140 225 L 125 224 L 117 223 L 111 222 L 105 221 L 91 218 L 80 215 L 77 213 L 74 213 L 66 210 L 64 208 L 62 205 L 63 205 L 65 203 L 80 194 L 87 189 L 92 185 L 97 181 L 112 166 L 114 163 L 116 160 L 117 158 L 118 156 L 119 153 L 120 150 L 120 141 L 119 138 L 118 135 L 116 132 L 110 126 L 105 123 L 100 121 L 97 120 L 89 119 L 80 119 L 72 120 L 65 122 L 62 123 L 57 125 L 53 127 L 47 130 L 44 132 L 41 134 L 36 138 L 29 145 L 26 149 L 24 152 L 20 160 L 19 163 L 18 167 L 17 172 L 17 178 L 18 183 L 19 187 L 20 190 L 24 198 L 27 201 L 28 204 L 26 206 L 24 207 L 22 208 L 17 210 L 12 212 L 4 215 L 0 216 L 0 233 L 2 232 L 13 229 L 21 226 L 26 224 L 37 219 L 41 216 L 44 216 L 46 217 L 52 221 L 58 224 L 65 227 L 71 229 L 80 232 L 87 234 L 96 236 L 101 237 L 112 239 L 120 240 L 128 241 L 165 241 L 172 240 L 178 239 L 187 237 L 191 236 L 194 234 L 197 234 L 205 231 L 219 224 L 224 221 L 227 219 L 230 217 L 234 214 L 238 211 L 247 206 L 246 217 L 247 221 L 248 224 L 249 226 L 250 228 L 256 234 L 259 236 L 262 237 L 279 237 L 284 236 L 292 233 L 294 232 L 296 231 L 305 225 L 310 221 L 315 216 L 315 214 L 314 212 L 311 208 L 309 204 L 308 201 L 305 202 L 300 208 L 294 213 L 291 215 L 285 218 L 282 219 L 279 220 L 275 221 L 266 221 L 263 218 L 262 214 L 262 209 L 263 208 L 263 202 L 264 197 L 265 193 L 267 187 L 270 178 L 273 170 L 277 162 L 282 154 L 287 144 L 289 139 L 292 131 L 292 128 L 294 125 L 295 122 L 295 119 L 297 116 L 299 109 L 305 87 L 308 70 L 310 66 L 313 52 L 313 47 L 315 42 L 318 26 L 318 21 L 319 20 L 319 16 L 318 14 L 315 11 L 313 10 Z
M 239 144 L 244 144 L 245 145 L 251 145 L 255 146 L 257 147 L 259 148 L 263 153 L 262 155 L 259 161 L 253 170 L 250 174 L 247 178 L 242 184 L 233 193 L 227 198 L 223 201 L 218 204 L 210 208 L 205 210 L 198 212 L 194 213 L 179 213 L 177 212 L 175 211 L 171 207 L 170 205 L 169 203 L 168 199 L 168 192 L 169 188 L 171 184 L 174 178 L 178 173 L 185 166 L 190 162 L 193 160 L 196 158 L 203 154 L 205 154 L 207 152 L 212 150 L 221 147 L 226 146 L 231 145 Z
M 75 136 L 94 136 L 100 139 L 103 142 L 103 149 L 100 155 L 86 169 L 81 173 L 77 176 L 67 183 L 64 185 L 61 187 L 46 196 L 44 196 L 40 192 L 37 188 L 36 186 L 35 184 L 34 180 L 34 171 L 35 167 L 36 164 L 39 159 L 44 153 L 46 151 L 51 147 L 54 145 L 57 143 L 65 139 L 68 138 Z
"""
IA_D = """M 38 58 L 35 59 L 32 62 L 31 64 L 30 67 L 28 74 L 27 82 L 26 86 L 25 90 L 23 93 L 22 100 L 20 105 L 18 110 L 15 116 L 12 121 L 10 124 L 7 128 L 2 133 L 0 136 L 0 157 L 2 155 L 3 155 L 8 151 L 15 144 L 20 138 L 23 134 L 25 131 L 26 128 L 28 126 L 30 129 L 31 133 L 34 138 L 36 141 L 45 150 L 48 152 L 51 154 L 59 158 L 62 158 L 65 160 L 69 161 L 75 162 L 81 163 L 94 163 L 99 162 L 102 161 L 105 160 L 108 158 L 110 158 L 112 160 L 117 162 L 120 163 L 128 164 L 135 164 L 143 163 L 147 162 L 156 159 L 161 157 L 163 156 L 165 155 L 172 151 L 175 149 L 178 147 L 182 144 L 187 140 L 199 128 L 202 123 L 205 123 L 206 125 L 207 130 L 209 135 L 212 141 L 215 146 L 221 153 L 227 158 L 230 160 L 233 162 L 235 163 L 240 165 L 243 166 L 246 167 L 250 168 L 258 169 L 268 169 L 275 168 L 279 167 L 283 166 L 286 165 L 291 163 L 297 160 L 304 156 L 307 154 L 310 152 L 314 149 L 318 146 L 324 141 L 335 130 L 337 127 L 338 125 L 338 122 L 337 119 L 334 116 L 332 115 L 327 115 L 325 116 L 320 121 L 320 122 L 316 126 L 307 134 L 303 137 L 299 140 L 296 142 L 284 148 L 279 150 L 272 152 L 254 152 L 250 151 L 246 150 L 240 147 L 237 145 L 234 142 L 233 142 L 231 140 L 231 139 L 228 136 L 226 133 L 223 127 L 222 124 L 221 121 L 220 117 L 219 110 L 218 100 L 218 97 L 220 87 L 220 83 L 218 78 L 217 76 L 215 73 L 208 66 L 200 62 L 197 61 L 193 60 L 188 59 L 173 59 L 167 60 L 161 61 L 157 62 L 150 64 L 142 67 L 135 70 L 126 75 L 123 77 L 120 79 L 116 82 L 111 86 L 104 93 L 100 98 L 98 101 L 96 104 L 92 112 L 91 115 L 90 118 L 90 132 L 91 135 L 92 138 L 95 143 L 94 146 L 90 147 L 86 147 L 79 146 L 73 145 L 68 144 L 63 142 L 61 141 L 59 140 L 56 138 L 49 131 L 47 128 L 44 122 L 42 115 L 41 108 L 41 95 L 42 87 L 43 83 L 46 75 L 47 70 L 47 63 L 43 59 L 40 58 Z
M 177 75 L 185 75 L 191 76 L 194 77 L 196 78 L 198 79 L 202 83 L 202 90 L 200 95 L 194 107 L 192 110 L 189 114 L 186 118 L 177 127 L 171 132 L 167 135 L 162 138 L 150 144 L 147 145 L 140 147 L 124 147 L 119 145 L 117 144 L 109 136 L 108 134 L 107 132 L 106 129 L 106 122 L 107 119 L 108 116 L 109 114 L 112 109 L 117 103 L 120 100 L 126 95 L 130 92 L 133 90 L 136 88 L 140 86 L 146 83 L 153 80 L 156 80 L 159 78 L 164 77 L 169 76 Z
M 45 16 L 43 17 L 41 19 L 40 21 L 39 23 L 38 28 L 38 35 L 39 37 L 43 41 L 50 41 L 52 40 L 55 37 L 56 35 L 57 33 L 58 28 L 58 22 L 57 20 L 54 17 L 52 16 Z
"""

_ALEDIA_LOGO_SVG = f"""
<svg id="rb-header-logo"
     viewBox="-40 -40 887 420"
     xmlns="http://www.w3.org/2000/svg"
     style="height:30px;width:auto;display:block;cursor:pointer;flex-shrink:0;color:#c8a84b;overflow:visible;"
     role="img"
     aria-label="Aledia">

    <g id="logo-global" transform="translate(110 60)">

        <g id="logo-al" transform="translate(-222 -92) scale(1)">
            <path fill="currentColor" fill-rule="evenodd" d="{AL_D}"/>
        </g>

        <g id="logo-ed" transform="translate(215 -6) scale(1)">
            <path fill="currentColor" fill-rule="evenodd" d="{ED_D}"/>
        </g>

        <g id="logo-ia" transform="translate(524 57) scale(1)">
            <path fill="currentColor" fill-rule="evenodd" d="{IA_D}"/>
        </g>

    </g>

</svg>
"""

_CSS = """
<style>
/* ── Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

*, *::before, *::after { box-sizing:border-box; margin:0; padding:0; }

:root {
  /* ── Palette LUMIÈRE ── */
  --navy:      #0d1b3e;
  --navy-d:    #0a1530;
  --navy-m:    #122052;
  --navy-l:    #1a2f6a;
  --gold:      #c9a84c;
  --gold-l:    #e8c97a;
  --slate-50:  #f8f9fc;
  --slate-100: #eef0f6;
  --slate-200: #d8dce8;
  --slate-400: #8892aa;
  --slate-600: #4a5568;
  --bg:        #f8f9fc;
  --surface:   #ffffff;
  --text:      #0d1b3e;
  --border:    #e2e6f0;
  --radius:    8px;
  --shadow:    0 1px 3px rgba(13,27,62,.08), 0 1px 2px rgba(13,27,62,.04);
  --fm:        'IBM Plex Mono', 'Courier New', monospace;
  --fd:        'DM Sans', 'Helvetica Neue', Arial, sans-serif;
  --fb:        'DM Sans', 'Helvetica Neue', Arial, sans-serif;
  /* Hauteur du header + nav — référencées partout */
  --hdr-h:     62px;
  --sep-h:     10px;
  --nav-h:     44px;
  --top-h:     calc(var(--hdr-h) + var(--sep-h) + var(--nav-h));
}

body {
  font-family: var(--fb);
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  overflow-y: scroll;
  /* compense header + sep + tabbar fixed */
  padding-top: var(--top-h);
}

/* ══════════════════════════════════════════════════
   HEADER — fixe, compact
══════════════════════════════════════════════════ */
.rb-header {
  background: linear-gradient(90deg, #060e22 0%, #0d1b3e 30%, #122052 65%, #1a2f6a 100%);
  padding: 0 20px;
  height: var(--hdr-h);
  min-height: var(--hdr-h);
  max-height: var(--hdr-h);
  display: flex;
  align-items: center;
  gap: 0;
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 200;
  overflow: hidden;
}

/* Bloc gauche : logo SVG Aledia + séparateur + Lumière */
.rb-header-brand-block {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-right: 20px;
  margin-right: 20px;
  flex-shrink: 0;
}

/* Logo SVG Aledia — currentColor pour l'easter egg (animation color) */
#rb-header-logo {
  transition: color .35s ease;
}

/* Séparateur vertical interne brand-block */
.rb-header-sep {
  width: 1px;
  height: 34px;
  background: rgba(255,255,255,.2);
  flex-shrink: 0;
  margin: 0;
}

/* "LUMIÈRE" + acronyme */
.rb-header-lumiere {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.rb-header-lumiere-name {
  font-family: var(--fb);
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 6px;
  text-transform: uppercase;
  color: #ffffff;
  line-height: 1;
}
.rb-header-lumiere-full {
  font-size: 9.5px;
  color: rgba(255,255,255,.5);
  letter-spacing: .2px;
  line-height: 1;
  white-space: nowrap;
  font-weight: 400;
}
.rb-header-lumiere-full em {
  font-style: normal;
  font-weight: 500;
  color: rgba(200,168,75,.85);
}

/* Titre du rapport — prend l'espace restant */
.rb-header-title {
  font-family: var(--fb);
  font-size: 13px;
  font-weight: 500;
  color: rgba(255,255,255,.92);
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rb-header-title span {
  font-size: 11px;
  font-weight: 300;
  color: rgba(255,255,255,.4);
  margin-left: 8px;
}

/* Méta auteur · date */
.rb-header-meta {
  font-family: var(--fm);
  font-size: 9px;
  color: rgba(255,255,255,.4);
  letter-spacing: .05em;
  text-align: right;
  white-space: nowrap;
  flex-shrink: 0;
}

.rb-header-info-btn {
  margin-left: auto;
  background: none;
  border: 1px solid rgba(212,175,55,.45);
  border-radius: 50%;
  color: var(--gold);
  font-size: 1rem;
  width: 28px;
  height: 28px;
  cursor: pointer;
  line-height: 1;
  transition: color .2s, border-color .2s, background .2s;
  flex-shrink: 0;
}

.rb-header-info-btn:hover {
  color: var(--gold-l);
  border-color: var(--gold);
  background: rgba(212,175,55,.08);
}

/* ══════════════════════════════════════════════════
   BARRE DE SÉPARATION HEADER → NAV  (glow gold)
══════════════════════════════════════════════════ */
.rb-nav-separator {
  height: var(--sep-h);
  background: #060e22;
  position: fixed;
  top: var(--hdr-h);
  left: 0; right: 0;
  z-index: 199;
  overflow: hidden;
}
.rb-nav-separator::before {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(255,255,255,.04);
}
.rb-sep-glow {
  position: absolute;
  top: 0; bottom: 0;
  width: 340px;
  pointer-events: none;
  transition: left .32s cubic-bezier(.4,0,.2,1);
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(232,201,122,.12) 12%,
    rgba(232,201,122,.55) 30%,
    #e8c97a 48%,
    #f2dc8a 50%,
    #e8c97a 52%,
    rgba(232,201,122,.55) 70%,
    rgba(232,201,122,.12) 88%,
    transparent 100%
  );
}

/* ── Nav / Tab bar ── */
.rb-tabbar {
  background: #060e22;
  padding: 0 20px;
  display: flex;
  align-items: center;
  gap: 0;
  position: fixed;
  top: calc(var(--hdr-h) + var(--sep-h));
  left: 0; right: 0;
  z-index: 198;
  height: var(--nav-h);
}
.rb-tab-btn {
  font-family: var(--fb);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: .1px;
  color: rgba(255,255,255,.55);
  padding: 0 15px;
  height: 100%;
  border: none;
  background: none;
  cursor: pointer;
  transition: color .18s;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  position: relative;
  z-index: 1;
  user-select: none;
}
.rb-tab-btn:hover { color: rgba(255,255,255,.88); }
.rb-tab-btn.active { color: #ffffff; font-weight: 600; }
.rb-tab-btn svg { fill: currentColor; flex-shrink: 0; }

/* ── Tab panels ── */
.rb-tab-panel { display: none; }
.rb-tab-panel.active { display: block; overflow-y: auto; }
/* Tab GraphBuilderV2 — hauteur fixe, pas de scroll page */
.rb-tab-panel.gb-panel {
  display: none;
  height: calc(100vh - var(--top-h));
  overflow: hidden;
  position: relative;
}
.rb-tab-panel.gb-panel.active {
  display: flex;
  flex-direction: column;
}

/* ── Report body ── */
.rb-body {
  max-width: 100%;
  margin: 0;
  padding: 16px 28px 80px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ══════════════════════════════════════════════════
   LAYOUT — Row & Grid (mode page)
══════════════════════════════════════════════════ */

.pg-row {
  display: grid;
  width: 100%;
}

.pg-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.pg-grid {
  display: grid;
  width: 100%;
}

.pg-grid-cell {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.pg-grid-cell-empty {
  background: transparent;
}

/* ── Section ── */
.rb-section { display:flex; align-items:center; gap:10px; padding-top:4px; }
.rb-section-bar { width:2px; height:16px; background:var(--gold); flex-shrink:0; }
.rb-section h2 { font-family:var(--fd); font-weight:400; font-size:13px; color:var(--text); letter-spacing:.01em; }
.rb-section-sub { font-family:var(--fm); font-size:9px; color:var(--slate-400); margin-left:4px; }

/* ── Text ── */
.rb-text {
  background:var(--surface); border:0.5px solid var(--border);
  border-left: 2px solid var(--gold);
  border-radius: 0 var(--radius) var(--radius) 0;
  padding: 14px 18px;
  font-size: 12px; line-height: 1.7; color: var(--slate-600);
}
.rb-text h1,.rb-text h2,.rb-text h3 { font-family:var(--fd); font-weight:500; color:var(--text); margin-bottom:6px; }
.rb-text p { margin-bottom:8px; }
.rb-text strong { color:var(--text); font-weight:500; }
.rb-text code { font-family:var(--fm); background:var(--slate-100); padding:1px 5px; border-radius:3px; font-size:11px; }

/* ── KPI Row ── */
.rb-kpi-row {
  display: grid;
  grid-auto-columns: minmax(0, 1fr);
  grid-auto-flow: column;
  gap: 8px;
}
.rb-kpi {
  background:var(--surface); border:0.5px solid var(--border);
  border-radius:var(--radius); padding:14px 16px;
  position:relative; overflow:hidden;
}
.rb-kpi::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:var(--gold); }
.rb-kpi-label { font-family:var(--fm); font-size:9px; letter-spacing:.08em; text-transform:uppercase; color:var(--slate-400); margin-bottom:6px; }
.rb-kpi-value { font-family:var(--fd); font-size:22px; font-weight:300; color:var(--text); line-height:1; letter-spacing:-.02em; }
.rb-kpi-unit  { font-family:var(--fm); font-size:11px; color:var(--slate-400); margin-left:2px; }
.rb-kpi-delta { font-family:var(--fm); font-size:9px; margin-top:5px; display:inline-block; padding:2px 6px; border-radius:20px; }
.rb-kpi-delta.pos { background:#eaf3de; color:#3b6d11; }
.rb-kpi-delta.neg { background:#faeeda; color:#854f0b; }
.rb-kpi-delta.neu { background:var(--slate-100); color:var(--slate-400); }
.rb-kpi-sub { font-size:9px; color:var(--slate-400); margin-top:4px; }

/* ── Generic chart wrap ── */
.rb-chart-wrap {
  background:var(--surface); border:0.5px solid var(--border);
  border-radius:var(--radius); padding:8px;
  overflow:hidden;
}
.rb-chart-caption { font-family:var(--fm); font-size:9px; color:var(--slate-400); padding:4px 10px 6px; }

/* ── DataTable ── */
.rb-table-wrap { background:var(--surface); border:0.5px solid var(--border); border-radius:var(--radius); overflow:hidden; }
.rb-table-toolbar { display:flex; align-items:center; justify-content:space-between; padding:9px 14px; border-bottom:0.5px solid var(--border); gap:10px; }
.rb-table-title { font-family:var(--fd); font-size:12px; font-weight:500; color:var(--text); }
.rb-table-search { font-family:var(--fm); font-size:10px; padding:4px 10px; border:0.5px solid var(--border); border-radius:var(--radius); outline:none; width:180px; transition:border-color .15s; }
.rb-table-search:focus { border-color:var(--gold); }
.rb-table-count { font-family:var(--fm); font-size:9px; color:var(--slate-400); white-space:nowrap; }
.rb-table-scroll { overflow-x:auto; }
table.rb-table { width:100%; border-collapse:collapse; font-size:11px; }
table.rb-table thead tr { background:var(--navy); }
table.rb-table thead th { padding:8px 12px; text-align:left; font-family:var(--fm); font-size:9px; font-weight:400; letter-spacing:.08em; text-transform:uppercase; color:rgba(255,255,255,.65); white-space:nowrap; cursor:pointer; user-select:none; transition:background .12s; }
table.rb-table thead th:hover { background:var(--navy-l); }
table.rb-table thead th .sort-icon { display:inline-block; margin-left:4px; opacity:.35; font-size:8px; }
table.rb-table thead th.sorted-asc .sort-icon,
table.rb-table thead th.sorted-desc .sort-icon { opacity:1; color:var(--gold); }
table.rb-table tbody tr { border-bottom:0.5px solid var(--border); transition:background .1s; }
table.rb-table tbody tr:last-child { border-bottom:none; }
table.rb-table tbody tr:hover { background:var(--slate-50); }
table.rb-table td { padding:7px 12px; font-family:var(--fm); font-size:10px; color:var(--slate-600); }
table.rb-table td.rb-num { text-align:right; color:var(--text); font-weight:500; }
.rb-table-footer { display:flex; align-items:center; justify-content:space-between; padding:7px 14px; border-top:0.5px solid var(--border); font-family:var(--fm); font-size:9px; color:var(--slate-400); }
.rb-pagination { display:flex; gap:3px; }
.rb-page-btn { padding:3px 8px; border:0.5px solid var(--border); border-radius:4px; background:none; font-family:var(--fm); font-size:9px; cursor:pointer; transition:all .12s; }
.rb-page-btn:hover { background:var(--slate-100); }
.rb-page-btn.active { background:var(--navy); color:#fff; border-color:var(--navy); }
.rb-page-btn:disabled { opacity:.35; cursor:not-allowed; }

/* ════════════════════════════════════════
   LED BLOCKS — shared panel chrome
════════════════════════════════════════ */
.led-block {
  background:var(--surface); border:1px solid var(--border);
  border-radius:var(--radius); overflow:hidden;
  box-shadow:var(--shadow);
}
.led-block-header {
  display:flex; align-items:center; gap:10px;
  padding:10px 16px; border-bottom:1px solid var(--border);
  background:var(--slate-50);
}
.led-block-num { font-family:var(--fm); font-size:9px; color:var(--gold-l); background:var(--navy); padding:2px 7px; letter-spacing:.05em; }
.led-block-title { font-family:var(--fd); font-weight:700; font-size:12px; color:var(--navy); text-transform:uppercase; letter-spacing:.1em; flex:1; }
.led-block-sub { font-family:var(--fm); font-size:9px; color:var(--slate-400); letter-spacing:.06em; }
.led-block-rule { height:1px; margin:0 16px; background:linear-gradient(90deg,var(--gold) 0%,var(--border) 25%,transparent 100%); }

/* ── ScatterLED ── */
.scatter-led-wrap { position:relative; }
.scatter-led-toolbar {
  display:flex; align-items:center; gap:8px;
  padding:8px 16px; border-bottom:1px solid var(--border);
}
.slt-btn {
  font-family:var(--fm); font-size:9px; color:var(--slate-600);
  background:var(--slate-100); border:1px solid var(--border);
  padding:4px 10px; cursor:pointer; letter-spacing:.06em;
  transition:all .15s; display:flex; align-items:center; gap:5px;
}
.slt-btn:hover { background:var(--slate-200); color:var(--navy); border-color:var(--slate-400); }
.slt-btn.active { background:var(--navy); color:var(--gold-l); border-color:var(--navy); }
.slt-sep { width:1px; height:16px; background:var(--border); }
.slt-count { font-family:var(--fm); font-size:9px; color:var(--slate-400); margin-left:auto; }
.slt-count.has-sel { color:var(--gold); }

/* ── ScatterLED layout — full width, detail below ── */
.sled-layout { display:block; }
.sled-main { }
.sled-detail-col {
  border-top:2px solid var(--border);
  background:var(--slate-50);
  position:relative;
  overflow:hidden;
  max-height:0;
  transition:max-height .38s cubic-bezier(.4,0,.2,1);
}
.sled-detail-col::before {
  content:''; position:absolute; top:0; left:0; right:0; height:2px;
  background:linear-gradient(90deg,var(--gold),rgba(212,175,55,.2) 50%,transparent 80%);
}
.sled-detail-col.open { max-height:520px; }

/* ── Detail inner ── */
.led-detail-inner {
  height:520px;
  display:flex; flex-direction:column;
  padding:8px 16px 12px;
  overflow:hidden;
}
.led-detail-header { display:flex; align-items:center; gap:10px; margin-bottom:8px; flex-shrink:0; }
.led-detail-label { font-family:var(--fm); font-size:10px; color:var(--navy); flex:1; letter-spacing:.06em; }
.led-detail-label span { color:var(--gold); margin-right:6px; }
.led-detail-close {
  font-family:var(--fm); font-size:9px; color:var(--slate-400); cursor:pointer;
  padding:3px 8px; border:1px solid var(--border); background:var(--surface);
  transition:all .15s; letter-spacing:.04em;
}
.led-detail-close:hover { color:var(--navy); border-color:var(--navy); }
.led-detail-plots { flex:1; display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; min-height:0; }
.led-sub-wrap {
  background:var(--surface); border:1px solid var(--border);
  display:flex; flex-direction:column; overflow:hidden; position:relative;
}
.led-sub-wrap::before { content:''; position:absolute; top:0; left:0; width:3px; height:100%; }
.led-sub-wrap--jv::before   { background:#3B82F6; }
.led-sub-wrap--eqe::before  { background:var(--gold); }
.led-sub-wrap--spec::before { background:#8B5CF6; }
.led-sub-hdr { padding:5px 10px 0 12px; display:flex; justify-content:space-between; align-items:center; flex-shrink:0; }
.led-sub-title { font-family:var(--fd); font-weight:700; font-size:10px; color:var(--navy); text-transform:uppercase; letter-spacing:.08em; }
.led-sub-axes { font-family:var(--fm); font-size:8px; color:var(--slate-400); }
.led-sub-body { flex:1; min-height:0; }
.led-sub-body > div { height:100%; }
.no-data-msg { height:100%; display:flex; align-items:center; justify-content:center; font-family:var(--fm); font-size:9px; color:var(--slate-400); letter-spacing:.08em; }

/* ── SummaryBoxPlots ── */
.summary-grid { display:grid; gap:12px; }
.summary-grid-2 { grid-template-columns:1fr 1fr; }
.summary-grid-3 { grid-template-columns:1fr 1fr 1fr; }
.summary-plot-card {
  background:var(--surface); border:1px solid var(--border);
  border-radius:var(--radius); overflow:hidden; position:relative;
  box-shadow:var(--shadow);
}
.summary-plot-label {
  position:absolute; top:8px; left:12px; z-index:2;
  font-family:var(--fd); font-weight:700; font-size:10px;
  color:var(--navy); text-transform:uppercase; letter-spacing:.08em;
}

/* ── WaferMaps ── */
.wafer-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(680px,1fr)); gap:16px; }
.wafer-card {
  background:var(--surface); border:1px solid var(--border);
  overflow:hidden; box-shadow:var(--shadow);
}
.wafer-card-header {
  padding:9px 16px; display:flex; align-items:center; gap:10px;
  border-bottom:1px solid var(--border); background:var(--slate-50);
}
.wafer-card-name { font-family:var(--fd); font-weight:700; font-size:11px; color:var(--navy); text-transform:uppercase; letter-spacing:.08em; flex:1; }
.wafer-card-count { font-family:var(--fm); font-size:10px; color:var(--slate-400); }
.wafer-card-body { display:grid; grid-template-columns:1fr 1fr; }
.wafer-card-map { border-right:1px solid var(--border); overflow:hidden; min-width:0; }
.wafer-card-map > div { height:320px; }
.wafer-card-curves { display:grid; grid-template-rows:1fr 1fr 1fr; gap:1px; background:var(--border); }
.wafer-card-curves > div { background:var(--surface); min-height:0; }
.wafer-card-foot {
  font-family:var(--fm); font-size:9px; color:var(--navy);
  padding:5px 14px; background:var(--slate-50); border-top:1px solid var(--border);
  letter-spacing:.06em;
}

/* ── WaferMap toolbar ── */
.wm-toolbar {
  display:flex; align-items:center; gap:6px; flex-wrap:wrap;
  padding:7px 12px; background:var(--slate-50);
  border-bottom:1px solid var(--border);
}
.wm-tool-label { font-family:var(--fm); font-size:9px; color:var(--slate-400); letter-spacing:.06em; text-transform:uppercase; }
.wm-select {
  height:26px; padding:0 22px 0 8px; font-family:var(--fm); font-size:10px;
  background:var(--surface); border:1px solid var(--border); border-radius:4px;
  color:var(--text); outline:none; appearance:none; cursor:pointer;
  transition:border-color .15s;
}
.wm-select:focus { border-color:var(--gold); }
.wm-select-wrap { position:relative; display:inline-flex; }
.wm-select-wrap::after { content:''; position:absolute; right:7px; top:50%; transform:translateY(-50%); width:0; height:0; border-left:3px solid transparent; border-right:3px solid transparent; border-top:4px solid var(--slate-400); pointer-events:none; }
.wm-btn {
  font-family:var(--fm); font-size:9px; color:var(--slate-600);
  background:var(--slate-100); border:1px solid var(--border);
  padding:3px 9px; cursor:pointer; letter-spacing:.06em; border-radius:4px;
  transition:all .15s; display:flex; align-items:center; gap:4px;
}
.wm-btn:hover { background:var(--slate-200); color:var(--navy); border-color:var(--slate-400); }
.wm-btn.active { background:var(--navy); color:var(--gold-l); border-color:var(--navy); }
.wm-sep { width:1px; height:16px; background:var(--border); margin:0 2px; }
.wm-sel-count { font-family:var(--fm); font-size:9px; color:var(--slate-400); margin-left:auto; }
.wm-sel-count.has-sel { color:var(--gold); }

/* ── WaferMap detail panel ── */
.wm-detail-panel {
  display:none; border-top:2px solid var(--border);
  background:var(--slate-50); position:relative;
}
.wm-detail-panel::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg,var(--gold),rgba(212,175,55,.2) 50%,transparent 80%); }
.wm-detail-panel.open { display:block; }
.wm-detail-inner { padding:10px 12px; display:grid; gap:8px; }
.wm-detail-grid { display:grid; grid-template-columns:180px 1fr 1fr; gap:8px; height:280px; }
.wm-led-list {
  background:var(--surface); border:1px solid var(--border);
  border-radius:4px; overflow-y:auto; display:flex; flex-direction:column;
}
.wm-led-list::-webkit-scrollbar { width:3px; }
.wm-led-list::-webkit-scrollbar-thumb { background:var(--border); border-radius:2px; }
.wm-led-list-header { font-family:var(--fm); font-size:9px; color:var(--muted); padding:6px 10px; border-bottom:1px solid var(--border); letter-spacing:.06em; text-transform:uppercase; background:var(--slate-50); flex-shrink:0; }
.wm-led-item {
  display:flex; align-items:center; gap:8px;
  padding:6px 10px; cursor:pointer; border-bottom:1px solid var(--border);
  transition:background .12s; font-family:var(--fm); font-size:10px; color:var(--text);
}
.wm-led-item:last-child { border-bottom:none; }
.wm-led-item:hover { background:var(--slate-50); }
.wm-led-item.active { background:rgba(10,36,99,.06); color:var(--navy); }
.wm-led-item-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.wm-led-item-name { font-weight:500; flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.wm-led-item-val { font-size:9px; color:var(--muted); }
.wm-kpi-agg-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(120px,1fr)); gap:6px; padding:8px 0; }
.wm-kpi-agg {
  background:var(--surface); border:1px solid var(--border); border-radius:4px; padding:8px 10px;
  position:relative; overflow:hidden;
}
.wm-kpi-agg::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:var(--gold); }
.wm-kpi-agg-label { font-family:var(--fm); font-size:8px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin-bottom:4px; }
.wm-kpi-agg-val { font-family:var(--fd); font-size:16px; font-weight:800; color:var(--navy); line-height:1; }
.wm-kpi-agg-std { font-family:var(--fm); font-size:9px; color:var(--muted); margin-top:2px; }

/* ── ScatterSummary ── */
.ss-wrap { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow); overflow:hidden; }
.ss-header { display:flex; align-items:center; gap:10px; padding:10px 16px; border-bottom:1px solid var(--border); background:var(--slate-50); }

/* ════════════════════════════════════════
   GRAPH BUILDER
════════════════════════════════════════ */
.gb-sidebar {
  background:var(--surface); border-right:1px solid var(--border);
  overflow-y:auto; overflow-x:hidden; padding:12px 10px 24px;
}
.gb-sidebar::-webkit-scrollbar { width:3px; }
.gb-sidebar::-webkit-scrollbar-thumb { background:var(--border); border-radius:2px; }
.gb-resize-handle {
  width:4px; background:var(--border); cursor:col-resize;
  transition:background .15s; flex-shrink:0; position:relative;
  display:flex; align-items:center; justify-content:center;
}
.gb-resize-handle:hover, .gb-resize-handle.dragging { background:var(--gold); }
.gb-resize-handle::after {
  content:''; position:absolute;
  width:2px; height:24px; border-radius:2px;
  background:var(--slate-400); opacity:.5;
}
.gb-canvas {
  display:flex; flex-direction:column; gap:10px;
  padding:14px; background:var(--bg); overflow:hidden; min-height:0;
}
.gb-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); margin-bottom:8px; overflow:hidden; }
.gb-card-header { display:flex; align-items:center; gap:8px; padding:8px 12px; cursor:pointer; user-select:none; transition:background .15s; border-bottom:1px solid var(--border); }
.gb-card.collapsed .gb-card-header { border-bottom:none; }
.gb-card-header:hover { background:var(--slate-50); }
.gb-card-title { font-family:var(--fm); font-size:9px; font-weight:600; text-transform:uppercase; letter-spacing:.1em; color:var(--slate-400); flex:1; }
.gb-chevron { transition:transform .2s; fill:var(--slate-400); }
.gb-card.collapsed .gb-chevron { transform:rotate(-90deg); }
.gb-card-body { padding:10px 12px; }
.gb-card.collapsed .gb-card-body { display:none; }
.gb-row { margin-bottom:8px; }
.gb-label { font-size:9px; font-weight:600; color:var(--slate-400); text-transform:uppercase; letter-spacing:.08em; margin-bottom:3px; display:block; }
.gb-select, .gb-input {
  width:100%; height:29px; padding:0 24px 0 9px;
  background:var(--slate-50); border:1px solid var(--border);
  border-radius:var(--radius); color:var(--text);
  font-size:11px; font-family:var(--fm);
  outline:none; transition:border-color .15s; appearance:none; cursor:pointer;
}
.gb-select:focus, .gb-input:focus { border-color:var(--gold); }
.gb-select-wrap { position:relative; }
.gb-select-wrap::after { content:''; position:absolute; right:9px; top:50%; transform:translateY(-50%); width:0; height:0; border-left:4px solid transparent; border-right:4px solid transparent; border-top:5px solid var(--slate-400); pointer-events:none; }
.gb-badge {
  font-family:var(--fm); font-size:8px; padding:1px 5px;
  border-radius:3px; letter-spacing:.04em;
  display:inline-block; margin-left:4px;
}
.gb-badge-scalar { background:rgba(59,130,246,.1); color:#3B82F6; }
.gb-badge-vector { background:rgba(212,175,55,.1); color:var(--gold); }
.gb-types { display:grid; grid-template-columns:repeat(3,1fr); gap:4px; }
.gb-type-btn {
  display:flex; flex-direction:column; align-items:center; gap:3px;
  padding:6px 4px; background:var(--slate-50);
  border:1px solid var(--border); border-radius:var(--radius);
  cursor:pointer; transition:all .15s; color:var(--slate-400);
  font-family:var(--fm); font-size:8px; font-weight:600; text-transform:uppercase; letter-spacing:.06em;
}
.gb-type-btn svg { fill:currentColor; }
.gb-type-btn:hover { border-color:var(--navy); color:var(--navy); background:rgba(10,36,99,.04); }
.gb-type-btn.active { background:rgba(10,36,99,.07); border-color:var(--navy); color:var(--navy); }
.gb-type-btn.disabled { opacity:.35; pointer-events:none; }
.gb-toggle-row { display:flex; align-items:center; justify-content:space-between; margin-bottom:7px; }
.gb-toggle-label { font-size:11px; color:var(--text); }
.gb-toggle { width:30px; height:17px; border-radius:9px; background:#d1d5db; border:none; cursor:pointer; position:relative; transition:background .2s; flex-shrink:0; }
.gb-toggle::after { content:''; position:absolute; width:11px; height:11px; border-radius:50%; background:#fff; top:3px; left:3px; transition:transform .2s; box-shadow:0 1px 3px rgba(0,0,0,.3); }
.gb-toggle.on { background:var(--navy); }
.gb-toggle.on::after { transform:translateX(13px); }
.gb-mode-bar {
  display:flex; gap:4px; padding:6px 10px;
  background:var(--slate-50); border-bottom:1px solid var(--border);
}
.gb-mode-pill {
  font-family:var(--fm); font-size:9px; padding:3px 10px;
  border:1px solid var(--border); border-radius:20px;
  cursor:pointer; color:var(--slate-400); transition:all .15s;
}
.gb-mode-pill:hover { border-color:var(--navy); color:var(--navy); }
.gb-mode-pill.active { background:var(--navy); color:var(--gold-l); border-color:var(--navy); }
.gb-stats { display:flex; gap:12px; align-items:center; flex-shrink:0; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:6px 14px; }
.gb-stat { font-family:var(--fm); font-size:10px; color:var(--slate-400); }
.gb-stat strong { color:var(--navy); font-weight:500; }
.gb-stat-sep { width:1px; height:12px; background:var(--border); }
.gb-build-btn {
  font-family:var(--fm); font-size:10px; font-weight:600;
  letter-spacing:.06em; text-transform:uppercase;
  background:var(--navy); color:#fff; border:none;
  border-radius:var(--radius); padding:8px 18px;
  cursor:pointer; display:flex; align-items:center; gap:8px;
  transition:background .15s; flex-shrink:0;
}
.gb-build-btn:hover { background:var(--navy-l); }
.gb-build-btn svg { fill:currentColor; }
.gb-toolbar { display:flex; justify-content:space-between; align-items:center; flex-shrink:0; }
.gb-plot-wrap {
  flex:1; min-height:0;
  background:var(--surface); border:1px solid var(--border);
  border-radius:var(--radius); overflow:hidden;
  position:relative; box-shadow:var(--shadow);
}
.gb-plot-empty {
  position:absolute; inset:0;
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  gap:10px; color:var(--slate-400); pointer-events:none;
}
.gb-plot-empty svg { opacity:.12; fill:var(--navy); }
.gb-plot-empty p { font-family:var(--fm); font-size:11px; }

/* ── GraphBuilderV2 layout ── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
:root{
  --navy:#0A2463; --navy-l:#0d2f7a; --gold:#D4AF37; --gold-l:#E5C76B;
  --slate-50:#F8F9FD; --slate-100:#F0F3FC; --slate-200:#E4E8F4;
  --slate-400:#8B97BF; --slate-600:#4A5580;
  --bg:#D8DCE8; --surface:#FFFFFF; --text:#1a1a2e; --border:#E4E8F4;
  --radius:6px; --shadow:0 1px 4px rgba(10,36,99,.08),0 4px 16px rgba(10,36,99,.06);
  --fm:'IBM Plex Mono',monospace; --fd:'Syne',sans-serif; --fb:'DM Sans',sans-serif;
}
body{font-family:var(--fb);background:var(--bg);color:var(--text);height:100vh;overflow:hidden;display:flex;flex-direction:column;}

.gb-header{
  height:48px;background:var(--surface);border-bottom:1px solid var(--border);
  display:flex;align-items:center;padding:0 20px;gap:12px;flex-shrink:0;
  box-shadow:0 2px 8px rgba(10,36,99,.06);position:relative;
}
.gb-header::after{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,var(--gold),rgba(212,175,55,.2) 40%,transparent 70%);}
.gb-logo{font-family:var(--fd);font-weight:800;font-size:13px;color:var(--navy);letter-spacing:.12em;}
.gb-sep{width:1px;height:14px;background:var(--border);}
.gb-title{font-family:var(--fm);font-size:10px;color:var(--slate-400);letter-spacing:.1em;text-transform:uppercase;}

.gb-mode-tabs{display:flex;gap:2px;margin-left:auto;}
.gb-mode-tab{
  font-family:var(--fm);font-size:9px;letter-spacing:.08em;text-transform:uppercase;
  padding:6px 14px;border:1px solid var(--border);background:var(--slate-100);
  color:var(--slate-400);cursor:pointer;transition:all .15s;
}
.gb-mode-tab:hover{background:var(--slate-200);color:var(--navy);}
.gb-mode-tab.active{background:var(--navy);color:var(--gold-l);border-color:var(--navy);}

.gb-main{display:flex;min-height:0;overflow:hidden;height:calc(100vh - 48px);}

.gb-fragment-wrap{
  display:flex;
  flex-direction:column;
  flex:1;
  min-height:0;
  overflow:hidden;
  height:100%;
}
.gb-fragment-wrap > .gb-mode-bar{
  flex-shrink:0;
  background:var(--surface);
  border-bottom:2px solid var(--navy);
}
.gb-fragment-wrap .gb-main{
  flex:1;
  min-height:0;
  height:auto;
}
.gb-fragment-wrap #table-view{
  flex:1;
  min-height:0;
}

.gb-sidebar{
  width:280px;flex-shrink:0;background:var(--surface);border-right:1px solid var(--border);
  overflow-y:auto;overflow-x:hidden;display:flex;flex-direction:column;
}
.gb-sidebar::-webkit-scrollbar{width:3px;}
.gb-sidebar::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px;}

.gb-section{border-bottom:1px solid var(--border);}
.gb-section-hdr{
  display:flex;align-items:center;gap:8px;padding:10px 14px;cursor:pointer;
  font-family:var(--fm);font-size:9px;font-weight:600;text-transform:uppercase;
  letter-spacing:.1em;color:var(--slate-400);user-select:none;
  transition:background .12s;
}
.gb-section-hdr:hover{background:var(--slate-50);}
.gb-section-hdr svg{fill:var(--slate-400);flex-shrink:0;transition:transform .2s;}
.gb-section.open .gb-section-hdr svg.chevron{transform:rotate(-180deg);}
.gb-section-body{display:none;padding:10px 14px;gap:8px;flex-direction:column;}
.gb-section.open .gb-section-body{display:flex;}

.gb-row{display:flex;flex-direction:column;gap:3px;}
.gb-label{font-family:var(--fm);font-size:9px;color:var(--slate-400);text-transform:uppercase;letter-spacing:.08em;}
.gb-select,.gb-input{
  width:100%;height:28px;padding:0 22px 0 8px;font-family:var(--fm);font-size:10px;
  background:var(--slate-50);border:1px solid var(--border);border-radius:var(--radius);
  color:var(--text);outline:none;transition:border-color .15s;appearance:none;cursor:pointer;
}
.gb-select:focus,.gb-input:focus{border-color:var(--gold);}
.gb-select-wrap{position:relative;}
.gb-select-wrap::after{content:'';position:absolute;right:8px;top:50%;transform:translateY(-50%);
  width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;
  border-top:5px solid var(--slate-400);pointer-events:none;}
.gb-badge{font-family:var(--fm);font-size:7px;padding:1px 5px;border-radius:3px;display:inline-block;margin-left:4px;}
.gb-badge-s{background:rgba(59,130,246,.1);color:#3B82F6;}
.gb-badge-v{background:rgba(212,175,55,.1);color:var(--gold);}
.gb-badge-c{background:rgba(139,92,246,.1);color:#8B5CF6;}

.gb-chart-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;}
.gb-ctype{
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:3px;padding:7px 4px;background:var(--slate-50);border:1px solid var(--border);
  border-radius:var(--radius);cursor:pointer;transition:all .15s;
  font-family:var(--fm);font-size:7px;text-transform:uppercase;letter-spacing:.04em;color:var(--slate-400);
}
.gb-ctype svg{fill:currentColor;}
.gb-ctype:hover{border-color:var(--navy);color:var(--navy);background:rgba(10,36,99,.04);}
.gb-ctype.active{background:var(--navy);color:var(--gold-l);border-color:var(--navy);}
.gb-ctype.disabled{opacity:.3;pointer-events:none;}

.gb-toggle-row{display:flex;align-items:center;justify-content:space-between;}
.gb-toggle-lbl{font-size:11px;color:var(--text);}
.gb-toggle{width:30px;height:17px;border-radius:9px;background:#d1d5db;border:none;cursor:pointer;
  position:relative;transition:background .2s;flex-shrink:0;}
.gb-toggle::after{content:'';position:absolute;width:11px;height:11px;border-radius:50%;background:#fff;
  top:3px;left:3px;transition:transform .2s;box-shadow:0 1px 3px rgba(0,0,0,.3);}
.gb-toggle.on{background:var(--navy);}
.gb-toggle.on::after{transform:translateX(13px);}

.gb-range{width:100%;accent-color:var(--navy);}

.gb-filter-row{display:flex;gap:4px;align-items:center;margin-bottom:5px;}
.gb-filter-row .gb-select-wrap{flex:1.2;}
.gb-filter-row .gb-select-wrap:nth-child(2){flex:.7;}
.gb-rm-btn{width:22px;height:28px;border:1px solid var(--border);background:none;
  border-radius:4px;color:var(--slate-400);cursor:pointer;font-size:14px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;transition:all .12px;}
.gb-rm-btn:hover{border-color:#EF4444;color:#EF4444;}
.gb-add-filter{width:100%;padding:6px;border:1px dashed var(--border);border-radius:var(--radius);
  background:none;font-family:var(--fm);font-size:9px;color:var(--slate-400);cursor:pointer;
  transition:all .15s;letter-spacing:.06em;}
.gb-add-filter:hover{border-color:var(--navy);color:var(--navy);}

.gb-build-wrap{padding:12px 14px;border-top:1px solid var(--border);margin-top:auto;flex-shrink:0;}
.gb-build-btn{
  width:100%;padding:10px;border:none;border-radius:var(--radius);
  background:var(--navy);color:#fff;font-family:var(--fm);font-size:11px;
  font-weight:600;letter-spacing:.08em;text-transform:uppercase;
  cursor:pointer;transition:background .15s;display:flex;align-items:center;justify-content:center;gap:8px;
}
.gb-build-btn:hover{background:var(--navy-l);}

.gb-statsbar{
  padding:6px 14px;background:var(--slate-50);border-bottom:1px solid var(--border);
  display:flex;gap:16px;flex-shrink:0;
}
.gb-stat{font-family:var(--fm);font-size:9px;color:var(--slate-400);}
.gb-stat strong{color:var(--navy);font-weight:500;}

.gb-canvas{
  flex:1;min-width:0;min-height:0;display:flex;flex-direction:column;
  background:var(--bg);gap:8px;padding:12px;overflow:hidden;
}
.gb-status-bar{
  display:flex;align-items:center;gap:8px;flex-shrink:0;
  padding:6px 12px;background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);font-family:var(--fm);font-size:10px;color:var(--slate-400);
}
.gb-status-dot{width:6px;height:6px;border-radius:50%;background:var(--border);flex-shrink:0;}
.gb-status-dot.ok{background:#10B981;}
.gb-status-dot.err{background:#EF4444;}
.gb-plot-area{
  flex:1;min-height:0;background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);overflow:hidden;position:relative;box-shadow:var(--shadow);
}
.gb-plot-empty{
  position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:12px;color:var(--slate-400);pointer-events:none;
}
.gb-plot-empty svg{opacity:.08;fill:var(--navy);}
.gb-plot-empty p{font-family:var(--fm);font-size:11px;letter-spacing:.06em;}
#gb-plot{position:absolute;inset:0;width:100%;height:100%;}

.gb-resize{width:4px;background:var(--border);cursor:col-resize;flex-shrink:0;
  transition:background .15s;}
.gb-resize:hover,.gb-resize.drag{background:var(--gold);}

#tbl-main thead tr{background:var(--navy);}
#tbl-main thead th{
  padding:9px 12px;text-align:left;
  font-family:var(--fm);font-size:9px;font-weight:500;
  letter-spacing:.08em;text-transform:uppercase;color:rgba(255,255,255,.75);
  white-space:nowrap;cursor:pointer;user-select:none;
  position:sticky;top:0;background:var(--navy);
  transition:background .12s;
}
#tbl-main thead th:hover{background:var(--navy-l);}
#tbl-main thead th.sort-asc::after{content:' ▲';color:var(--gold);font-size:8px;}
#tbl-main thead th.sort-desc::after{content:' ▼';color:var(--gold);font-size:8px;}
#tbl-main tbody tr{border-bottom:1px solid var(--border);transition:background .1s;}
#tbl-main tbody tr:hover{background:var(--slate-50);}
#tbl-main tbody tr.tbl-excluded{opacity:.35;background:#fff5f5;}
#tbl-main tbody td{
  padding:7px 12px;font-family:var(--fm);font-size:10px;color:var(--slate-600);
  white-space:nowrap;max-width:180px;overflow:hidden;text-overflow:ellipsis;
}
#tbl-main tbody td.tbl-num{color:var(--navy);font-weight:500;text-align:right;}
#tbl-main tbody td.tbl-computed{color:#7c3aed;}
.tbl-excl-btn{
  padding:2px 7px;border:1px solid var(--border);background:none;
  border-radius:3px;font-family:var(--fm);font-size:9px;
  cursor:pointer;color:var(--slate-400);transition:all .12s;
  white-space:nowrap;
}
.tbl-excl-btn:hover{border-color:#EF4444;color:#EF4444;background:#fef2f2;}
.tbl-excl-btn.excluded{border-color:#EF4444;color:#EF4444;background:#fef2f2;}
.tbl-restore-btn{
  padding:2px 7px;border:1px solid #10B981;background:rgba(16,185,129,.1);
  border-radius:3px;font-family:var(--fm);font-size:9px;
  cursor:pointer;color:#059669;transition:all .12s;white-space:nowrap;
}

/* ── ScatterPoint : barre unifiée sélection + filtres ──────────────────── */
.spt-combined-toolbar {
    display: flex;
    align-items: center;
    gap: 0;
    padding: 0 12px;
    height: 36px;
    border-bottom: 1px solid rgba(10, 36, 99, .08);
    background: rgba(10, 36, 99, .025);
    overflow-x: auto;
    flex-wrap: nowrap;
}
.spt-toolbar-group {
    display: flex;
    align-items: center;
    gap: 5px;
    flex-shrink: 0;
}
.spt-toolbar-divider {
    width: 1px;
    height: 18px;
    background: rgba(10, 36, 99, .15);
    margin: 0 10px;
    flex-shrink: 0;
}
.spt-filter-label {
    font-family: "IBM Plex Mono", monospace;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: .1em;
    color: rgba(10, 36, 99, .45);
    text-transform: uppercase;
    margin-right: 2px;
    flex-shrink: 0;
}
.spt-filter-axis-tag {
    font-family: "IBM Plex Mono", monospace;
    font-size: 10px;
    font-weight: 600;
    color: #0A2463;
    background: rgba(212, 175, 55, .15);
    border: 1px solid rgba(212, 175, 55, .4);
    border-radius: 3px;
    padding: 1px 5px;
    white-space: nowrap;
    max-width: 110px;
    overflow: hidden;
    text-overflow: ellipsis;
    flex-shrink: 0;
}
.spt-filter-op {
    font-family: "IBM Plex Mono", monospace;
    font-size: 11px;
    height: 24px;
    padding: 0 4px;
    border: 1px solid rgba(10, 36, 99, .2);
    border-radius: 4px;
    background: white;
    color: #0A2463;
    cursor: pointer;
    flex-shrink: 0;
    min-width: 42px;
}
.spt-filter-op:focus { outline: none; border-color: #D4AF37; }
.spt-filter-val {
    font-family: "IBM Plex Mono", monospace;
    font-size: 11px;
    height: 24px;
    width: 72px;
    padding: 0 6px;
    border: 1px solid rgba(10, 36, 99, .2);
    border-radius: 4px;
    color: #0A2463;
    flex-shrink: 0;
}
.spt-filter-val:focus { outline: none; border-color: #D4AF37; box-shadow: 0 0 0 2px rgba(212, 175, 55, .2); }
.spt-filter-val::placeholder { color: rgba(10, 36, 99, .3); }
.spt-filter-sep { font-size: 14px; color: rgba(10, 36, 99, .25); flex-shrink: 0; padding: 0 2px; }
.slt-btn--gold {
    background: rgba(212, 175, 55, .12) !important;
    border-color: rgba(212, 175, 55, .5) !important;
    color: #8a6e00 !important;
    font-weight: 600 !important;
}
.slt-btn--gold:hover { background: rgba(212, 175, 55, .25) !important; }
.spt-filt-count { font-family: "IBM Plex Mono", monospace; font-size: 10px; font-weight: 600; min-width: 48px; flex-shrink: 0; }
.spt-filt-active { color: #EF4444; }
.spt-filt-ok     { color: #10B981; }
.spt-selcount { font-size: 10px; min-width: 80px; }

/* ── ScatterLED : barre de filtres multi-colonnes ──────────────────────── */
.sled-filter-bar { border-top: 1px solid rgba(10, 36, 99, .08); background: rgba(10, 36, 99, .02); padding: 8px 12px; }
.sled-filter-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
.sled-filter-rows { display: flex; flex-direction: column; gap: 5px; }
.sled-frow { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.sled-fctrl { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; flex: 1; }
.sled-fchk-wrap { display: flex; flex-wrap: wrap; gap: 4px; }
.sled-fchk-label {
    display: flex; align-items: center; gap: 3px;
    font-family: "IBM Plex Mono", monospace; font-size: 10px; color: #0A2463;
    background: rgba(10, 36, 99, .06); border: 1px solid rgba(10, 36, 99, .15);
    border-radius: 3px; padding: 2px 7px; cursor: pointer; user-select: none;
    transition: background .15s, border-color .15s;
}
.sled-fchk-label:hover { background: rgba(10, 36, 99, .12); }
.sled-fchk-label:has(input:checked) { background: rgba(212, 175, 55, .18); border-color: rgba(212, 175, 55, .6); color: #7a5c00; font-weight: 600; }
.sled-fchk { display: none; }

/* ══════════════════════════════════════════════════
   MODE SLIDE — layout 16:9
══════════════════════════════════════════════════ */
body.rb-mode-slide { background: #1a2245; overflow: hidden; }
.sv-wrapper { width:100vw; height:100vh; position:relative; overflow:hidden; }
.sv-slide { position:absolute; inset:0; display:none; flex-direction:column; background:#ffffff; }
.sv-slide.active { display:flex; }
.sv-slide.sv-slide-special { background:var(--navy); }
.sv-slide-topbar { height:4px; min-height:4px; flex-shrink:0; background:linear-gradient(90deg,#c8a84b 0%,#7090d0 50%,#232E5B 100%); }
.sv-slide-titlebar { padding:14px 28px 8px; flex-shrink:0; }
.sv-slide-title { font-family:var(--fb); font-size:26px; font-weight:700; color:var(--navy); text-transform:uppercase; letter-spacing:-.01em; }
.sv-slide-body { flex:1; min-height:0; display:grid; grid-template-columns:1fr; padding:0 28px 0; overflow:hidden; }
.sv-slide-body > .rb-body { overflow-y:auto; padding:8px 0; }
.sv-slide-body-special { padding:0; display:flex; align-items:stretch; }
.sv-slide-footer { height:38px; min-height:38px; flex-shrink:0; background:#e8e8e4; border-top:1px solid #d0d0cc; display:flex; align-items:center; justify-content:space-between; padding:0 28px; }
.sv-footer-left { font-family:var(--fm); font-size:10px; color:#aaa; letter-spacing:.05em; min-width:160px; }
.sv-footer-nav { display:flex; align-items:center; gap:10px; }
.sv-nav-btn { font-size:16px; color:#888; background:none; border:none; cursor:pointer; padding:0 4px; line-height:1; transition:color .15s; }
.sv-nav-btn:hover:not(:disabled) { color:var(--navy); }
.sv-nav-btn:disabled { opacity:.25; cursor:not-allowed; }
.sv-slide-index { font-family:var(--fb); font-size:15px; font-weight:600; color:var(--navy); letter-spacing:.02em; white-space:nowrap; min-width:80px; text-align:right; }
.sv-dots { display:flex; gap:5px; align-items:center; }
.sv-dot { width:5px; height:5px; border-radius:50%; background:rgba(35,46,91,.2); cursor:pointer; transition:background .2s, transform .2s; }
.sv-dot.active { background:var(--gold); transform:scale(1.3); }
.sv-dot:hover:not(.active) { background:rgba(35,46,91,.45); }
.sv-grid { display:grid; width:100%; height:100%; padding:8px 0 8px; }
.sv-cell { background:var(--navy); border-radius:14px; overflow:hidden; position:relative; min-height:0; }
.sv-cell-empty { background:rgba(35,46,91,.15); border:1px dashed rgba(35,46,91,.2); }
.sv-cell-inner { width:100%; height:100%; overflow:auto; padding:14px 16px; color:rgba(255,255,255,.85); }
.sv-cell-inner .rb-kpi-row { gap:8px; }
.sv-cell-inner .rb-kpi { background:rgba(255,255,255,.08); border-color:rgba(255,255,255,.12); }
.sv-cell-inner .rb-kpi-value { color:#fff; }
.sv-cell-inner .rb-kpi-label { color:rgba(255,255,255,.5); }
.sv-cell-inner .rb-section h2 { color:#fff; }
.sv-cell-inner .rb-text { background:rgba(255,255,255,.06); border-color:rgba(255,255,255,.12); color:rgba(255,255,255,.8); border-left-color:var(--gold); }
.sv-cell-inner .js-plotly-plot,
.sv-cell-inner .plot-container { width:100% !important; height:100% !important; }
.sv-title-page { display:flex; align-items:stretch; width:100%; height:100%; position:relative; overflow:hidden; background:var(--navy); }
.sv-title-deco { position:absolute; right:0; top:0; bottom:0; width:38%; background:linear-gradient(135deg, rgba(200,168,75,.18) 0%, rgba(42,127,212,.25) 100%); clip-path:polygon(12% 0%, 100% 0%, 100% 100%, 0% 100%); }
.sv-title-content { position:relative; z-index:2; display:flex; flex-direction:column; justify-content:center; padding:0 0 0 10%; flex:1; }
.sv-title-eyebrow { font-family:var(--fm); font-size:11px; font-weight:500; letter-spacing:.2em; text-transform:uppercase; color:var(--gold); margin-bottom:20px; }
.sv-title-main { font-family:var(--fb); font-size:42px; font-weight:700; color:#fff; line-height:1.1; letter-spacing:-.02em; max-width:55%; margin-bottom:12px; }
.sv-title-sub { font-family:var(--fb); font-size:17px; font-weight:300; color:rgba(255,255,255,.6); margin-bottom:28px; max-width:50%; }
.sv-title-divider { width:48px; height:2px; background:linear-gradient(90deg,var(--gold),transparent); margin-bottom:18px; }
.sv-title-meta { font-family:var(--fm); font-size:11px; color:rgba(255,255,255,.4); letter-spacing:.06em; }
.sv-section-page { display:flex; align-items:center; justify-content:center; width:100%; height:100%; background:linear-gradient(135deg, var(--navy) 0%, var(--navy-l) 100%); }
.sv-section-content { text-align:center; }
.sv-section-label { font-family:var(--fm); font-size:10px; font-weight:500; letter-spacing:.25em; text-transform:uppercase; color:var(--gold); margin-bottom:16px; }
.sv-section-title { font-family:var(--fb); font-size:48px; font-weight:700; color:#fff; text-transform:uppercase; letter-spacing:-.01em; line-height:1.05; }
.sv-section-sub { font-family:var(--fb); font-size:18px; font-weight:300; color:rgba(255,255,255,.55); margin-top:14px; }
.sv-summary-page { display:flex; flex-direction:column; justify-content:center; width:100%; height:100%; padding:0 10%; background:var(--navy); }
.sv-summary-heading { font-family:var(--fb); font-size:13px; font-weight:500; letter-spacing:.2em; text-transform:uppercase; color:var(--gold); margin-bottom:28px; }
.sv-summary-list { display:flex; flex-direction:column; gap:6px; }
.sv-summary-section { font-family:var(--fb); font-size:11px; font-weight:600; letter-spacing:.15em; text-transform:uppercase; color:var(--gold); margin-top:14px; margin-bottom:2px; padding-left:0; }
.sv-summary-item { display:flex; align-items:baseline; gap:14px; padding:5px 0; border-bottom:0.5px solid rgba(255,255,255,.07); }
.sv-summary-num { font-family:var(--fm); font-size:12px; font-weight:500; color:rgba(255,255,255,.3); min-width:26px; }
.sv-summary-label { font-family:var(--fb); font-size:15px; font-weight:300; color:rgba(255,255,255,.85); }

.tab-initial { color: var(--gold); font-weight: 600; }
.rb-tab-btn { display: flex; align-items: center; gap: 0px; }

</style>
"""


_PLOTLY_CFG_JS = """{
  responsive:true, displaylogo:false,
  modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"],
}"""

_SHARED_LAYOUT_JS = """{
  paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"#F8F9FD",
  font:{family:"IBM Plex Mono, monospace", color:"#4A5580", size:11},
}"""

_GRID_STYLE_JS = """{
  gridcolor:"#E4E8F4", linecolor:"#E4E8F4", zerolinecolor:"#E4E8F4",
}"""