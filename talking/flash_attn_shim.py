"""Stand-in for the flash_attn package, which does not build on the RTX 5090 machines.
Same calls, done with the attention built into torch (which picks its fast path by itself).
Copied to LongCat-Video/flash_attn/__init__.py by setup_longcat.sh when the real package is missing."""
import torch
import torch.nn.functional as F

__version__ = "shim"


def flash_attn_func(q, k, v, dropout_p=0.0, softmax_scale=None, causal=False, **kw):
    # q, k, v arrive as (batch, sequence, heads, dim); torch wants (batch, heads, sequence, dim)
    out = F.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2),
                                         dropout_p=dropout_p, is_causal=causal, scale=softmax_scale)
    return out.transpose(1, 2)


def flash_attn_varlen_func(q, k, v, cu_seqlens_q, cu_seqlens_k, max_seqlen_q=None, max_seqlen_k=None,
                           dropout_p=0.0, softmax_scale=None, causal=False, **kw):
    # Several sequences packed end to end: q is (total_q, heads, dim), k and v are (total_k, heads, dim).
    # Each sequence only looks at its own keys.
    cq, ck = cu_seqlens_q.tolist(), cu_seqlens_k.tolist()
    outs = []
    for i in range(len(cq) - 1):
        qi = q[cq[i]:cq[i + 1]].transpose(0, 1).unsqueeze(0)      # (1, heads, len, dim)
        ki = k[ck[i]:ck[i + 1]].transpose(0, 1).unsqueeze(0)
        vi = v[ck[i]:ck[i + 1]].transpose(0, 1).unsqueeze(0)
        oi = F.scaled_dot_product_attention(qi, ki, vi, dropout_p=dropout_p, is_causal=causal, scale=softmax_scale)
        outs.append(oi.squeeze(0).transpose(0, 1))
    return torch.cat(outs, dim=0)
